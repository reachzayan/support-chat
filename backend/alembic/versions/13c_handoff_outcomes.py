"""handoff_outcomes table

Revision ID: 13chandoffout
Revises: 13bhandoffctx
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "13chandoffout"
down_revision: str | Sequence[str] | None = "13bhandoffctx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "handoff_outcomes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("handoff_id", sa.Uuid(), nullable=False),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('resolved','callback_completed','no_response','abandoned','duplicate')",
            name="ck_handoff_outcomes_outcome",
        ),
        sa.ForeignKeyConstraint(["handoff_id"], ["handoff_contexts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handoff_id", name="uq_handoff_outcomes_handoff"),
    )


def downgrade() -> None:
    op.drop_table("handoff_outcomes")
