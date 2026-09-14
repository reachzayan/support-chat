"""Grounded response approvals, citation spans, and per-site rollout flag.

Revision ID: 20groundedv2
Revises: 19applogs
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20groundedv2"
down_revision: str | Sequence[str] | None = "19applogs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column(
        "sites",
        sa.Column(
            "grounded_outcomes_v2", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "kb_chunks",
        sa.Column(
            "review_status",
            sa.String(),
            server_default=sa.text("'legacy_unreviewed'"),
            nullable=False,
        ),
    )
    op.add_column(
        "kb_chunks",
        sa.Column(
            "reviewed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )
    op.add_column("kb_chunks", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kb_chunks", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column(
        "kb_chunks",
        sa.Column("content_hash", sa.String(), server_default=sa.text("''"), nullable=False),
    )
    op.add_column(
        "kb_chunks",
        sa.Column("risk_class", sa.String(), server_default=sa.text("'general'"), nullable=False),
    )
    op.add_column(
        "kb_chunks",
        sa.Column(
            "answer_mode",
            sa.String(),
            server_default=sa.text("'paraphrase_allowed'"),
            nullable=False,
        ),
    )
    op.add_column("kb_chunks", sa.Column("topic_label", sa.String(), nullable=True))
    op.execute(
        "UPDATE kb_chunks SET approved = false, review_status = 'legacy_unreviewed', "
        "content_hash = encode(sha256(convert_to(answer_verbatim, 'UTF8')), 'hex')"
    )
    op.alter_column("kb_chunks", "approved", server_default=sa.text("false"))
    op.create_check_constraint(
        "ck_kb_chunks_review_status",
        "kb_chunks",
        "review_status IN ('legacy_unreviewed','pending','approved','rejected')",
    )
    op.create_check_constraint(
        "ck_kb_chunks_risk_class",
        "kb_chunks",
        "risk_class IN ('general','regulated','credential','pricing','timing','legal')",
    )
    op.create_check_constraint(
        "ck_kb_chunks_answer_mode",
        "kb_chunks",
        "answer_mode IN ('paraphrase_allowed','verbatim_only','human_only')",
    )
    op.create_check_constraint(
        "ck_kb_chunks_approval_review",
        "kb_chunks",
        "approved = false OR (review_status = 'approved' AND reviewed_by IS NOT NULL "
        "AND reviewed_at IS NOT NULL AND topic_label IS NOT NULL AND btrim(topic_label) <> '')",
    )
    op.drop_constraint("ck_kb_snapshots_state", "kb_snapshots", type_="check")
    op.create_check_constraint(
        "ck_kb_snapshots_state",
        "kb_snapshots",
        "state IN ('building','validated','awaiting_review','live','superseded','failed')",
    )
    op.add_column("messages", sa.Column("response_outcome", sa.String(), nullable=True))
    op.add_column("messages", sa.Column("response_reason_code", sa.String(), nullable=True))
    op.create_check_constraint(
        "ck_messages_response_outcome",
        "messages",
        "response_outcome IS NULL OR response_outcome IN "
        "('exact_answer','synthesized_answer','clarification','partial_answer','knowledge_gap','boundary')",
    )
    op.create_table(
        "message_citations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("response_start", sa.Integer(), nullable=False),
        sa.Column("response_end", sa.Integer(), nullable=False),
        sa.Column("source_start", sa.Integer(), nullable=False),
        sa.Column("source_end", sa.Integer(), nullable=False),
        sa.Column("cited_text", sa.Text(), nullable=False),
        sa.Column("source_title", sa.String(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "response_start >= 0 AND response_end >= response_start",
            name="ck_message_citations_response_offsets",
        ),
        sa.CheckConstraint(
            "source_start >= 0 AND source_end >= source_start",
            name="ck_message_citations_source_offsets",
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["kb_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["kb_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_citations_message_id", "message_citations", ["message_id"])
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY ix_kb_chunks_grounded_trgm ON kb_chunks USING gin "
            "(lower(coalesce(canonical_question, '') || ' ' || kb_aliases_as_text(aliases) || ' ' "
            "|| coalesce(heading, '') || ' ' || coalesce(topic_label, '')) gin_trgm_ops)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_kb_chunks_grounded_trgm")
    op.drop_index("ix_message_citations_message_id", table_name="message_citations")
    op.drop_table("message_citations")
    op.drop_constraint("ck_messages_response_outcome", "messages", type_="check")
    op.drop_column("messages", "response_reason_code")
    op.drop_column("messages", "response_outcome")
    op.drop_constraint("ck_kb_snapshots_state", "kb_snapshots", type_="check")
    op.create_check_constraint(
        "ck_kb_snapshots_state",
        "kb_snapshots",
        "state IN ('building','validated','live','superseded','failed')",
    )
    op.drop_constraint("ck_kb_chunks_approval_review", "kb_chunks", type_="check")
    op.drop_constraint("ck_kb_chunks_answer_mode", "kb_chunks", type_="check")
    op.drop_constraint("ck_kb_chunks_risk_class", "kb_chunks", type_="check")
    op.drop_constraint("ck_kb_chunks_review_status", "kb_chunks", type_="check")
    op.alter_column("kb_chunks", "approved", server_default=sa.text("true"))
    op.drop_column("kb_chunks", "topic_label")
    op.drop_column("kb_chunks", "answer_mode")
    op.drop_column("kb_chunks", "risk_class")
    op.drop_column("kb_chunks", "content_hash")
    op.drop_column("kb_chunks", "review_note")
    op.drop_column("kb_chunks", "reviewed_at")
    op.drop_column("kb_chunks", "reviewed_by")
    op.drop_column("kb_chunks", "review_status")
    op.drop_column("sites", "grounded_outcomes_v2")
