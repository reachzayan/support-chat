"""handoff_contexts table

Revision ID: 13bhandoffctx
Revises: 13aescalreason
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "13bhandoffctx"
down_revision: str | Sequence[str] | None = "13aescalreason"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ESCALATION_REASONS = (
    "visitor_request",
    "sensitive",
    "individual_case",
    "retrieval_miss",
    "sufficiency_fail",
    "provider_timeout",
    "repeated_miss",
    "policy_boundary",
    "rate_ceiling",
    "off_topic",
)


def upgrade() -> None:
    reasons = ", ".join(f"'{item}'" for item in _ESCALATION_REASONS)
    op.create_table(
        "handoff_contexts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("escalation_reason", sa.Text(), nullable=False),
        sa.Column("original_question", sa.Text(), nullable=False),
        sa.Column("clarification_answer", sa.Text(), nullable=True),
        sa.Column("machine_summary", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("machine_summary_model", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "candidate_unit_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column(
            "rejection_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "provider_stage_timings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("provider_status", sa.Text(), nullable=False),
        sa.Column("promised_response_by", sa.DateTime(timezone=True), nullable=True),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            f"escalation_reason IN ({reasons})",
            name="ck_handoff_contexts_reason",
        ),
        sa.CheckConstraint(
            "provider_status IN ('ok','timeout','error','rate_limited')",
            name="ck_handoff_contexts_provider_status",
        ),
        sa.CheckConstraint(
            "route IN ('live_queue','callback')",
            name="ck_handoff_contexts_route",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["kb_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_handoff_contexts_conversation_created",
        "handoff_contexts",
        ["conversation_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_handoff_contexts_site_created",
        "handoff_contexts",
        ["site_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_handoff_contexts_site_created", table_name="handoff_contexts")
    op.drop_index("ix_handoff_contexts_conversation_created", table_name="handoff_contexts")
    op.drop_table("handoff_contexts")
