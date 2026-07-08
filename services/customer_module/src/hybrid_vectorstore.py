"""Hybrid (lexical + semantic) retrieval backing Vanna's training-data
store: pgvector for embeddings + Postgres full-text search for keyword
matching, combined via reciprocal rank fusion (RRF).

Kept on a separate database (VECTOR_DB_*) from the app's own business DB —
this only ever stores table DDL, documentation, and example SQL, never
real row data.

Deliberately fast (<200ms retrieval budget): a small local ONNX embedding
model (fastembed, no network call) and RRF instead of a cross-encoder
reranker, which would add a second, much slower model inference pass.
"""
import hashlib
import json

import psycopg2
from fastembed import TextEmbedding
from vanna.legacy.base import VannaBase

from src.config import settings

EMBEDDING_DIM = 384  # BAAI/bge-small-en-v1.5 output size
_RRF_K = 60  # standard reciprocal-rank-fusion damping constant
_KINDS = ("ddl", "documentation", "sql")


class HybridPGVectorStore(VannaBase):
    def __init__(self, config=None):
        VannaBase.__init__(self, config=config)
        self.n_results = (config or {}).get("n_results", settings.retrieval_top_k)
        self._embedder = TextEmbedding(model_name=settings.embedding_model)
        self._conn = psycopg2.connect(
            host=settings.vector_db_host,
            port=settings.vector_db_port,
            dbname=settings.vector_db_name,
            user=settings.vector_db_user,
            password=settings.vector_db_password,
        )
        self._conn.autocommit = True
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self._ensure_schema()

    def _ensure_schema(self):
        with self._conn.cursor() as cur:
            for kind in _KINDS:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS vanna_{kind} (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
                        embedding VECTOR({EMBEDDING_DIM}) NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT now()
                    )
                """)
                cur.execute(f"CREATE INDEX IF NOT EXISTS vanna_{kind}_tsv_idx ON vanna_{kind} USING GIN(tsv)")
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS vanna_{kind}_vec_idx "
                    f"ON vanna_{kind} USING hnsw (embedding vector_cosine_ops)"
                )

    def generate_embedding(self, data: str, **kwargs) -> list:
        return next(self._embedder.embed([data])).tolist()

    @staticmethod
    def _vector_literal(embedding: list) -> str:
        """pgvector's native text input format, e.g. "[0.1,0.2,0.3]".

        Passed as a plain string with an explicit ::vector cast in SQL —
        avoids relying on psycopg2/pgvector adapter auto-detection, which
        only kicks in for numpy arrays, not plain Python lists (a bare
        list gets sent as a generic numeric[] array instead).
        """
        return "[" + ",".join(repr(float(x)) for x in embedding) + "]"

    @staticmethod
    def _content_id(kind: str, content: str) -> str:
        """Deterministic id from content, not a random UUID — makes
        retraining idempotent. Re-inserting identical content (e.g. running
        train_vanna.py again) is a no-op instead of piling up duplicates.
        """
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]
        return f"{digest}-{kind}"

    def _insert(self, kind: str, content: str) -> str:
        _id = self._content_id(kind, content)
        embedding = self._vector_literal(self.generate_embedding(content))
        with self._conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO vanna_{kind} (id, content, embedding) VALUES (%s, %s, %s::vector) "
                f"ON CONFLICT (id) DO NOTHING",
                (_id, content, embedding),
            )
        return _id

    def _hybrid_search(self, kind: str, query: str) -> list:
        """Reciprocal rank fusion over a text-search ranked list and a
        vector-similarity ranked list, each pulled from a wider candidate
        pool than the final result count.
        """
        query_embedding = self._vector_literal(self.generate_embedding(query))
        pool = self.n_results * 4
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                WITH text_ranked AS (
                    SELECT id, content, ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(tsv, plainto_tsquery('english', %(q)s)) DESC
                    ) AS rank
                    FROM vanna_{kind}
                    WHERE tsv @@ plainto_tsquery('english', %(q)s)
                    LIMIT %(pool)s
                ),
                vector_ranked AS (
                    SELECT id, content, ROW_NUMBER() OVER (
                        ORDER BY embedding <=> %(qvec)s::vector
                    ) AS rank
                    FROM vanna_{kind}
                    ORDER BY embedding <=> %(qvec)s::vector
                    LIMIT %(pool)s
                ),
                fused AS (
                    SELECT id, content, SUM(1.0 / (%(k)s + rank)) AS score
                    FROM (
                        SELECT * FROM text_ranked
                        UNION ALL
                        SELECT * FROM vector_ranked
                    ) combined
                    GROUP BY id, content
                )
                SELECT content FROM fused ORDER BY score DESC LIMIT %(n)s
                """,
                {"q": query, "qvec": query_embedding, "pool": pool, "k": _RRF_K, "n": self.n_results},
            )
            return [row[0] for row in cur.fetchall()]

    # --- Vanna interface ---

    def add_ddl(self, ddl: str, **kwargs) -> str:
        return self._insert("ddl", ddl)

    def add_documentation(self, documentation: str, **kwargs) -> str:
        return self._insert("documentation", documentation)

    def add_question_sql(self, question: str, sql: str, **kwargs) -> str:
        payload = json.dumps({"question": question, "sql": sql})
        return self._insert("sql", payload)

    def get_related_ddl(self, question: str, **kwargs) -> list:
        return self._hybrid_search("ddl", question)

    def get_related_documentation(self, question: str, **kwargs) -> list:
        return self._hybrid_search("documentation", question)

    def get_similar_question_sql(self, question: str, **kwargs) -> list:
        return [json.loads(r) for r in self._hybrid_search("sql", question)]

    def get_training_data(self, **kwargs):
        import pandas as pd

        rows = []
        with self._conn.cursor() as cur:
            for kind in _KINDS:
                cur.execute(f"SELECT id, content FROM vanna_{kind}")
                rows.extend(
                    {"id": _id, "training_data_type": kind, "content": content}
                    for _id, content in cur.fetchall()
                )
        return pd.DataFrame(rows)

    def remove_training_data(self, id: str, **kwargs) -> bool:
        kind = id.rsplit("-", 1)[-1]
        if kind not in _KINDS:
            return False
        with self._conn.cursor() as cur:
            cur.execute(f"DELETE FROM vanna_{kind} WHERE id = %s", (id,))
            return cur.rowcount > 0
