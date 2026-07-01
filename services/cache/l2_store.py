import sys
sys.path.insert(0, "/app")

import hashlib
import logging

from fastembed import TextEmbedding
from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.engine import get_session
from db.models.l2_cache import L2Cache

logger = logging.getLogger(__name__)


def init_db() -> None:
    """No-op: schema is managed by Alembic migrations."""
    pass


SIMILARITY_THRESHOLD = 0.82
NON_CACHEABLE = {"escalation", "unknown", "greeting"}

_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

_embed_cache: dict[str, list[float]] = {}
_EMBED_CACHE_MAX = 512


def _hash(query: str) -> str:
    return hashlib.md5(query.strip().lower().encode()).hexdigest()


def _embed(text: str) -> list[float]:
    if text in _embed_cache:
        return _embed_cache[text]
    result = list(list(_model.embed([text]))[0])
    if len(_embed_cache) >= _EMBED_CACHE_MAX:
        _embed_cache.pop(next(iter(_embed_cache)))
    _embed_cache[text] = result
    return result


def get(query: str, portal_id: str, frontend_version: str, intent: str) -> dict | None:
    if intent in NON_CACHEABLE:
        return None
    try:
        vec = _embed(query)
        with get_session() as session:
            row = session.execute(
                select(
                    L2Cache,
                    (1 - L2Cache.embedding.cosine_distance(vec)).label("score"),
                )
                .where(
                    L2Cache.portal_id == portal_id,
                    L2Cache.frontend_version == frontend_version,
                )
                .order_by(L2Cache.embedding.cosine_distance(vec))
                .limit(1)
            ).first()

            if row and float(row.score) >= SIMILARITY_THRESHOLD:
                row.L2Cache.hits += 1
                return {
                    "answer": row.L2Cache.answer,
                    "intent": row.L2Cache.intent,
                    "score": float(row.score),
                }
    except Exception:
        logger.error("l2_store.get failed", exc_info=True)
    return None


def set(query: str, answer: str, portal_id: str, frontend_version: str, intent: str) -> None:
    if intent in NON_CACHEABLE:
        return
    try:
        vec = _embed(query)
        ins = pg_insert(L2Cache).values(
            portal_id=portal_id,
            frontend_version=frontend_version,
            query=query.strip(),
            query_hash=_hash(query),
            answer=answer,
            intent=intent,
            embedding=vec,
        )
        stmt = ins.on_conflict_do_update(
            constraint="uq_l2_cache_lookup",
            set_={"answer": ins.excluded.answer, "embedding": ins.excluded.embedding},
        )
        with get_session() as session:
            session.execute(stmt)
    except Exception:
        logger.error("l2_store.set failed", exc_info=True)


def invalidate_version(portal_id: str, old_version: str) -> int:
    try:
        with get_session() as session:
            result = session.execute(
                delete(L2Cache).where(
                    L2Cache.portal_id == portal_id,
                    L2Cache.frontend_version == old_version,
                )
            )
            return result.rowcount
    except Exception:
        logger.error("l2_store.invalidate_version failed", exc_info=True)
        return 0


def top_queries(portal_id: str, frontend_version: str, limit: int = 50) -> list[dict]:
    try:
        with get_session() as session:
            rows = session.scalars(
                select(L2Cache)
                .where(
                    L2Cache.portal_id == portal_id,
                    L2Cache.frontend_version == frontend_version,
                )
                .order_by(L2Cache.hits.desc())
                .limit(limit)
            ).all()
            return [{"query": r.query, "answer": r.answer, "intent": r.intent} for r in rows]
    except Exception:
        logger.error("l2_store.top_queries failed", exc_info=True)
        return []


def stats(portal_id: str, frontend_version: str) -> dict:
    try:
        with get_session() as session:
            total = session.scalar(
                select(func.count()).select_from(L2Cache).where(
                    L2Cache.portal_id == portal_id,
                    L2Cache.frontend_version == frontend_version,
                )
            )
        return {"portal_id": portal_id, "frontend_version": frontend_version, "total_cached": total}
    except Exception:
        logger.error("l2_store.stats failed", exc_info=True)
        return {"error": "db unavailable"}
