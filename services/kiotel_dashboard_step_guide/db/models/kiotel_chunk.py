from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column, Mapped
from pgvector.sqlalchemy import Vector

from db.base import Base

EMBEDDING_DIM = 1024


class KiotelChunk(Base):
    __tablename__ = "kiotel_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    doc_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    doc_metadata: Mapped[dict] = mapped_column("doc_metadata", JSONB, nullable=False, default=dict)
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
