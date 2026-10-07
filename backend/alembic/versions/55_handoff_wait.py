"""Keep live handoffs queued until the visitor decides whether to wait."""

import sqlalchemy as sa

from alembic import op

revision = "55handoffwait"
down_revision = "54pushpreview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("handoff_wait_started_at", sa.DateTime(timezone=True)))
    op.add_column("conversations", sa.Column("handoff_wait_prompt_id", sa.BigInteger()))
    op.execute(
        "UPDATE conversations c SET handoff_wait_started_at = c.last_message_at "
        "FROM sites s WHERE c.site_id = s.id AND c.state = 'queued' AND s.human_enabled"
    )
    op.execute(
        "UPDATE notifications n SET in_app = false, read_at = coalesce(n.read_at, now()) "
        "FROM conversations c WHERE n.conversation_id = c.id AND c.state = 'closed'"
    )


def downgrade() -> None:
    op.drop_column("conversations", "handoff_wait_prompt_id")
    op.drop_column("conversations", "handoff_wait_started_at")
