"""Create knowledge_gaps and knowledge_gap_hits for the suggested-FAQ queue.

Revision ID: 46knowledgegaps
Revises: 45cannedbotknowledge
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "46knowledgegaps"
down_revision: str | Sequence[str] | None = "45cannedbotknowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_gaps",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("embedder_id", sa.String(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("status", sa.String(), server_default=sa.text("'open'"), nullable=False),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'canned', 'knowledge', 'dismissed')",
            name="ck_knowledge_gaps_status",
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "site_id", name="uq_knowledge_gaps_id_site"),
    )
    op.create_index("ix_knowledge_gaps_site_status", "knowledge_gaps", ["site_id", "status"])

    op.create_table(
        "knowledge_gap_hits",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("gap_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(
            ["conversation_id", "site_id"],
            ["conversations.id", "conversations.site_id"],
            name="fk_knowledge_gap_hits_conversation_site",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id", "site_id"],
            ["messages.id", "messages.site_id"],
            name="fk_knowledge_gap_hits_message_site",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["gap_id", "site_id"],
            ["knowledge_gaps.id", "knowledge_gaps.site_id"],
            name="fk_knowledge_gap_hits_gap_site",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_knowledge_gap_hits_message"),
    )
    op.create_index(
        "ix_knowledge_gap_hits_gap_created", "knowledge_gap_hits", ["gap_id", "created_at"]
    )
    op.create_index(
        "ix_knowledge_gap_hits_pending",
        "knowledge_gap_hits",
        ["id"],
        postgresql_where=sa.text("gap_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_gap_hits_pending", table_name="knowledge_gap_hits")
    op.drop_index("ix_knowledge_gap_hits_gap_created", table_name="knowledge_gap_hits")
    op.drop_table("knowledge_gap_hits")
    op.drop_index("ix_knowledge_gaps_site_status", table_name="knowledge_gaps")
    op.drop_table("knowledge_gaps")
