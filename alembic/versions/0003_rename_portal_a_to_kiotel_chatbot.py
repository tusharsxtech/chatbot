"""rename portal_id 'portal_a' to 'kiotel_chatbot' in l2_cache

The portals/portal_a service was renamed to portals/kiotel_chatbot. Existing
l2_cache rows still tagged with the old portal_id would otherwise become
orphaned (unreachable by portal_id lookups, losing cached answers and hit
counts) since the app now reads/writes under the new portal_id.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE l2_cache SET portal_id = 'kiotel_chatbot' WHERE portal_id = 'portal_a'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE l2_cache SET portal_id = 'portal_a' WHERE portal_id = 'kiotel_chatbot'"
    )
