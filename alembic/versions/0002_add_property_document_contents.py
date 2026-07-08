"""create property_document_contents table (doc-chat-service)

Combines doc-chat-service's table into the shared chatbot Postgres instead of
a separate database — same server, different table from l2_cache/kiotel_chunks.
This is a local mirror for now, not the real kiosk-dashboard production table
(see services/workflow/db/init.sql); customer_module's actual business-DB
connection stays fully separate and read-only, unaffected by this migration.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "property_document_contents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("property_document_id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.String(10), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("updated_by_agent_id", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_property_document_contents_device_id",
        "property_document_contents",
        ["device_id"],
    )
    op.create_index(
        "idx_property_document_contents_updated_at",
        "property_document_contents",
        ["updated_at"],
    )

    # Sample seed data for local dev/testing — safe to remove, mirrors
    # services/workflow/db/init.sql.
    op.execute(
        """
        INSERT INTO property_document_contents
            (id, property_document_id, device_id, content_html, word_count, updated_by_agent_id)
        VALUES
            (1, 1, 'device-001',
             '<h1>Thermostat Manual</h1>'
             '<p>The thermostat supports schedules, <strong>eco mode</strong>, and remote control via the '
             'mobile app.</p>'
             '<h2>Reset instructions</h2>'
             '<p>To reset it, hold the power button for <strong>10 seconds</strong>.</p>'
             '<ul>'
             '<li>Eco mode reduces heating by 2 degrees during unoccupied hours</li>'
             '<li>Toggle it from Settings &gt; Eco Mode</li>'
             '</ul>',
             42, 'agent-01'),
            (2, 2, 'device-001',
             '<h1>Thermostat Troubleshooting</h1>'
             '<p>If the thermostat display is blank, check the batteries first.</p>'
             '<p>If it is unresponsive after a firmware update, perform a factory reset via '
             '<em>Settings &gt; Advanced &gt; Factory Reset</em>.</p>',
             28, 'agent-01'),
            (3, 3, 'device-002',
             '<h1>Camera Setup Guide</h1>'
             '<p>The security camera connects over <strong>2.4GHz Wi-Fi only</strong>.</p>'
             '<p>Pair it using the companion app QR scanner. Night vision activates automatically '
             'below 5 lux of ambient light.</p>',
             24, 'agent-02')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("property_document_contents")
