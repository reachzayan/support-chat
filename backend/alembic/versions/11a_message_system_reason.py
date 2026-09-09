"""messages system_reason citation metadata

Revision ID: 11asysreason1
Revises: 10bksnapshot1
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "11asysreason1"
down_revision: str | Sequence[str] | None = "10bksnapshot1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SYSTEM_REASONS = (
    "answer",
    "clarify",
    "escalate",
    "tech_fail",
    "policy_boundary",
    "out_of_scope",
    "insufficient",
    "sensitive",
)


def upgrade() -> None:
    op.add_column("messages", sa.Column("system_reason", sa.String(), nullable=True))
    op.add_column(
        "messages",
        sa.Column("source_urls", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column("messages", sa.Column("display_locator", sa.String(), nullable=True))
    op.add_column("messages", sa.Column("source_title", sa.String(), nullable=True))
    allowed = ", ".join(f"'{item}'" for item in _SYSTEM_REASONS)
    op.create_check_constraint(
        "ck_messages_system_reason",
        "messages",
        f"system_reason IS NULL OR system_reason IN ({allowed})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_messages_system_reason", "messages", type_="check")
    op.drop_column("messages", "source_title")
    op.drop_column("messages", "display_locator")
    op.drop_column("messages", "source_urls")
    op.drop_column("messages", "system_reason")
