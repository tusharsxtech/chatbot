import json
from typing import List, Optional

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

from configs.settings import get_settings
from configs.logging_config import get_logger
from src.ingestion.loader import Chunk
from src.ingestion.embedder import get_embedder

logger = get_logger(__name__)

_DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS kiotel_chunks (
    id          TEXT PRIMARY KEY,
    doc_id      TEXT NOT NULL,
    content     TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}',
    embedding   vector(1024)
);

CREATE INDEX IF NOT EXISTS kiotel_chunks_embedding_idx
    ON kiotel_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS kiotel_chunks_doc_id_idx
    ON kiotel_chunks (doc_id);
"""


def _get_conn() -> PgConnection:
    settings = get_settings()
    return psycopg2.connect(settings.pg_dsn)


class VectorStore:
    def __init__(self):
        self.embedder = get_embedder()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
            conn.commit()
        logger.info("pgvector_schema_ready")

    def add_chunks(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return
        texts = [c.content for c in chunks]
        embeddings = self.embedder.embed_documents(texts)

        rows = [
            (
                c.chunk_id,
                c.doc_id,
                c.content,
                json.dumps(c.metadata),
                embeddings[i],
            )
            for i, c in enumerate(chunks)
        ]

        sql = """
            INSERT INTO kiotel_chunks (id, doc_id, content, metadata, embedding)
            VALUES %s
            ON CONFLICT (id) DO UPDATE
                SET content   = EXCLUDED.content,
                    metadata  = EXCLUDED.metadata,
                    embedding = EXCLUDED.embedding
        """
        batch_size = 200
        with _get_conn() as conn:
            with conn.cursor() as cur:
                for i in range(0, len(rows), batch_size):
                    psycopg2.extras.execute_values(
                        cur,
                        sql,
                        rows[i : i + batch_size],
                        template="(%s, %s, %s, %s::jsonb, %s::vector)",
                    )
            conn.commit()
        logger.info("upserted_chunks", count=len(chunks))

    def similarity_search(
        self,
        query: str,
        top_k: int = 20,
        filter_metadata: Optional[dict] = None,
    ) -> List[dict]:
        query_embedding = self.embedder.embed_query(query)
        vec_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

        where_clause = ""
        params: list = [vec_literal, top_k]
        if filter_metadata:
            conditions = []
            for k, v in filter_metadata.items():
                conditions.append(f"metadata @> %s::jsonb")
                params.insert(-1, json.dumps({k: v}))
            where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"""
            SELECT
                content,
                metadata,
                GREATEST(0, 1 - (embedding <=> %s::vector)) AS score
            FROM kiotel_chunks
            {where_clause}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        params_final = [vec_literal] + params[1:-1] + [vec_literal, top_k]

        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params_final)
                rows = cur.fetchall()

        return [
            {
                "content": r["content"],
                "metadata": r["metadata"] if isinstance(r["metadata"], dict) else json.loads(r["metadata"]),
                "score": float(r["score"]),
            }
            for r in rows
        ]

    def count(self) -> int:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM kiotel_chunks")
                return cur.fetchone()[0]

    def delete_all(self) -> None:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM kiotel_chunks")
            conn.commit()
        logger.warning("all_chunks_deleted")