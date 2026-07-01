import json
from typing import List, Optional

from sqlalchemy import select, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from configs.logging_config import get_logger
from src.ingestion.loader import Chunk
from src.ingestion.embedder import get_embedder
from db.engine import get_session
from db.models.kiotel_chunk import KiotelChunk

logger = get_logger(__name__)


class VectorStore:
    def __init__(self):
        self.embedder = get_embedder()

    def add_chunks(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return
        texts = [c.content for c in chunks]
        embeddings = self.embedder.embed_documents(texts)

        rows = [
            {
                "id": c.chunk_id,
                "doc_id": c.doc_id,
                "content": c.content,
                "doc_metadata": c.metadata,
                "embedding": embeddings[i],
            }
            for i, c in enumerate(chunks)
        ]

        batch_size = 200
        with get_session() as session:
            for i in range(0, len(rows), batch_size):
                ins = pg_insert(KiotelChunk).values(rows[i : i + batch_size])
                stmt = ins.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "content": ins.excluded.content,
                        "doc_metadata": ins.excluded.doc_metadata,
                        "embedding": ins.excluded.embedding,
                    },
                )
                session.execute(stmt)

        logger.info("upserted_chunks", count=len(chunks))

    def similarity_search(
        self,
        query: str,
        top_k: int = 20,
        filter_metadata: Optional[dict] = None,
    ) -> List[dict]:
        query_embedding = self.embedder.embed_query(query)

        stmt = select(
            KiotelChunk.content,
            KiotelChunk.doc_metadata.label("doc_metadata"),
            (1 - KiotelChunk.embedding.cosine_distance(query_embedding)).label("score"),
        ).order_by(KiotelChunk.embedding.cosine_distance(query_embedding)).limit(top_k)

        if filter_metadata:
            for k, v in filter_metadata.items():
                stmt = stmt.where(KiotelChunk.doc_metadata.op("@>")(json.dumps({k: v})))

        with get_session() as session:
            rows = session.execute(stmt).fetchall()

        return [
            {
                "content": r.content,
                "metadata": r.doc_metadata if isinstance(r.doc_metadata, dict) else json.loads(r.doc_metadata),
                "score": max(0.0, float(r.score)),
            }
            for r in rows
        ]

    def count(self) -> int:
        with get_session() as session:
            return session.scalar(select(func.count()).select_from(KiotelChunk)) or 0

    def delete_all(self) -> None:
        with get_session() as session:
            session.execute(delete(KiotelChunk))
        logger.warning("all_chunks_deleted")
