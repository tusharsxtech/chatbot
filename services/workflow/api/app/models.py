from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PropertyDocumentContent(Base):
    """Read-only mapping onto a pre-existing table this service does not own
    (lives in the shared kiosk-dashboard production database, table name is
    plural: property_document_contents).

    The DB credentials used here have INSERT/UPDATE privilege on this table
    (they're the main dashboard app's role) — the real read-only guarantee
    is that every query in app.repository.get_property_document_content* runs
    inside a Postgres READ ONLY transaction (postgresql_readonly execution
    option), which Postgres enforces regardless of the role's grants.
    """

    __tablename__ = "property_document_contents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    property_document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    device_id: Mapped[str] = mapped_column(String(10), nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by_agent_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
