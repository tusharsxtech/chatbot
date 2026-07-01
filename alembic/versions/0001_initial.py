"""create l2_cache and kiotel_chunks tables

Revision ID: 0001
Revises:
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── l2_cache (semantic cache, 384-dim bge-small) ──────────────────────────
    op.create_table(
        "l2_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portal_id", sa.String(), nullable=False),
        sa.Column("frontend_version", sa.String(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_hash", sa.String(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("hits", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portal_id", "frontend_version", "query_hash",
            name="uq_l2_cache_lookup",
        ),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS l2_embedding_idx "
        "ON l2_cache USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # ── kiotel_chunks (RAG documents, 1024-dim bge-large) ─────────────────────
    op.create_table(
        "kiotel_chunks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("doc_id", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("doc_metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("kiotel_chunks_doc_id_idx", "kiotel_chunks", ["doc_id"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS kiotel_chunks_embedding_idx "
        "ON kiotel_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_table("kiotel_chunks")
    op.drop_table("l2_cache")
