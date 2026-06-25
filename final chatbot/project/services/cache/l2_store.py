import sys
sys.path.insert(0, "/app")

import os
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from fastembed import TextEmbedding

DSN = os.getenv("PG_DSN", "postgresql://chatbot:chatbot@postgres:5432/chatbot")
SIMILARITY_THRESHOLD = 0.82
NON_CACHEABLE = {"escalation", "unknown", "greeting"}
EMBEDDING_DIM = 384

_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def _conn():
    return psycopg2.connect(DSN)


def init_db() -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS l2_cache (
                    id SERIAL PRIMARY KEY,
                    portal_id TEXT NOT NULL,
                    frontend_version TEXT NOT NULL,
                    query TEXT NOT NULL,
                    query_hash TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    embedding vector({EMBEDDING_DIM}),
                    hits INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(portal_id, frontend_version, query_hash)
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS l2_embedding_idx ON l2_cache USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);")
        conn.commit()


def _hash(query: str) -> str:
    return hashlib.md5(query.strip().lower().encode()).hexdigest()


def _embed(text: str) -> list[float]:
    return list(list(_model.embed([text]))[0])


def _vec_str(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"


def get(query: str, portal_id: str, frontend_version: str, intent: str) -> dict | None:
    if intent in NON_CACHEABLE:
        return None
    try:
        vs = _vec_str(_embed(query))
        with _conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT answer, intent, query,
                           1 - (embedding <=> %s::vector) AS score
                    FROM l2_cache
                    WHERE portal_id = %s AND frontend_version = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT 1
                """, (vs, portal_id, frontend_version, vs))
                row = cur.fetchone()
                if row and float(row["score"]) >= SIMILARITY_THRESHOLD:
                    cur.execute(
                        "UPDATE l2_cache SET hits = hits + 1 WHERE portal_id=%s AND frontend_version=%s AND query_hash=%s",
                        (portal_id, frontend_version, _hash(row["query"]))
                    )
                    conn.commit()
                    return {"answer": row["answer"], "intent": row["intent"], "score": float(row["score"])}
    except Exception:
        pass
    return None


def set(query: str, answer: str, portal_id: str, frontend_version: str, intent: str) -> None:
    if intent in NON_CACHEABLE:
        return
    try:
        vs = _vec_str(_embed(query))
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO l2_cache (portal_id, frontend_version, query, query_hash, answer, intent, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (portal_id, frontend_version, query_hash) DO UPDATE
                    SET answer = EXCLUDED.answer, embedding = EXCLUDED.embedding
                """, (portal_id, frontend_version, query.strip(), _hash(query), answer, intent, vs))
            conn.commit()
    except Exception:
        pass


def invalidate_version(portal_id: str, old_version: str) -> int:
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM l2_cache WHERE portal_id=%s AND frontend_version=%s", (portal_id, old_version))
                deleted = cur.rowcount
            conn.commit()
            return deleted
    except Exception:
        return 0


def top_queries(portal_id: str, frontend_version: str, limit: int = 50) -> list[dict]:
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT query, answer, intent FROM l2_cache
                    WHERE portal_id=%s AND frontend_version=%s
                    ORDER BY hits DESC LIMIT %s
                """, (portal_id, frontend_version, limit))
                return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def stats(portal_id: str, frontend_version: str) -> dict:
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM l2_cache WHERE portal_id=%s AND frontend_version=%s", (portal_id, frontend_version))
                total = cur.fetchone()[0]
        return {"portal_id": portal_id, "frontend_version": frontend_version, "total_cached": total}
    except Exception:
        return {"error": "db unavailable"}