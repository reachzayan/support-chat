"""Durable bot-generation leases and handoff-summary jobs.

Revision ID: 41durablebackground
Revises: 40citationtenantfks
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "41durablebackground"
down_revision: str | Sequence[str] | None = "40citationtenantfks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("generation_created_at", sa.DateTime(timezone=True)))
    op.add_column(
        "conversations", sa.Column("generation_lease_expires_at", sa.DateTime(timezone=True))
    )
    op.create_index(
        "ix_conversations_generation_recovery",
        "conversations",
        ["generation_lease_expires_at", "generation_created_at"],
        postgresql_where=sa.text("active_generation_id IS NOT NULL"),
    )

    op.add_column(
        "handoff_contexts",
        sa.Column("summary_status", sa.String(), nullable=False, server_default="queued"),
    )
    op.add_column(
        "handoff_contexts",
        sa.Column("summary_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "handoff_contexts",
        sa.Column(
            "summary_next_run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "handoff_contexts", sa.Column("summary_lease_expires_at", sa.DateTime(timezone=True))
    )
    op.add_column("handoff_contexts", sa.Column("summary_error", sa.String(length=128)))
    op.create_check_constraint(
        "ck_handoff_contexts_summary_status",
        "handoff_contexts",
        "summary_status IN ('queued','running','completed','failed')",
    )
    op.create_index(
        "ix_handoff_contexts_summary_queue",
        "handoff_contexts",
        ["summary_status", "summary_next_run_at", "created_at"],
        postgresql_where=sa.text("summary_status IN ('queued','running')"),
    )


def downgrade() -> None:
    op.drop_index("ix_handoff_contexts_summary_queue", table_name="handoff_contexts")
    op.drop_constraint("ck_handoff_contexts_summary_status", "handoff_contexts", type_="check")
    op.drop_column("handoff_contexts", "summary_error")
    op.drop_column("handoff_contexts", "summary_lease_expires_at")
    op.drop_column("handoff_contexts", "summary_next_run_at")
    op.drop_column("handoff_contexts", "summary_attempts")
    op.drop_column("handoff_contexts", "summary_status")
    op.drop_index("ix_conversations_generation_recovery", table_name="conversations")
    op.drop_column("conversations", "generation_lease_expires_at")
    op.drop_column("conversations", "generation_created_at")
