"""Index visitor-scoped conversation history.

Revision ID: 37visitorhistoryindex
Revises: 36visitorlocationchecked
Create Date: 2026-09-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "37visitorhistoryindex"
down_revision: str | Sequence[str] | None = "36visitorlocationchecked"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversations_visitor_site_last_message
            ON conversations (visitor_id, site_id, last_message_at)
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_conversations_visitor_site_last_message")
