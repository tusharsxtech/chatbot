from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PropertyDocumentContent

# Forces Postgres to open a READ ONLY transaction for the statement, so any
# INSERT/UPDATE/DELETE against property_document_contents is rejected by the
# database itself, independent of what the app code above it does.
_READONLY = {"postgresql_readonly": True}


async def get_property_document_contents_for_device(
    session: AsyncSession,
    device_id: str,
    limit: int,
) -> list[PropertyDocumentContent]:
    """Fetch the most recently updated property_document_contents for a device."""
    stmt = (
        select(PropertyDocumentContent)
        .where(PropertyDocumentContent.device_id == device_id)
        .order_by(PropertyDocumentContent.updated_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt, execution_options=_READONLY)
    return list(result.scalars().all())
