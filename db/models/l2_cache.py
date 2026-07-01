from sqlalchemy import Integer, String, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from db.base import Base

EMBEDDING_DIM = 384


class L2Cache(Base):
    __tablename__ = "l2_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portal_id: Mapped[str] = mapped_column(String, nullable=False)
    frontend_version: Mapped[str] = mapped_column(String, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_hash: Mapped[str] = mapped_column(String, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    hits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("portal_id", "frontend_version", "query_hash", name="uq_l2_cache_lookup"),
    )
