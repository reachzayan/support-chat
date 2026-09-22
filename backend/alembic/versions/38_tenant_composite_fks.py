"""Enforce tenant-scoped composite foreign keys.

Revision ID: 38tenantcompositefks
Revises: 37visitorhistoryindex
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "38tenantcompositefks"
down_revision: str | Sequence[str] | None = "37visitorhistoryindex"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "uq_conversations_id_site",
            "conversations",
            ["id", "site_id"],
            unique=True,
            postgresql_concurrently=True,
        )
        op.create_index(
            "uq_kb_pages_id_site",
            "kb_pages",
            ["id", "site_id"],
            unique=True,
            postgresql_concurrently=True,
        )
    op.execute(
        "ALTER TABLE conversations ADD CONSTRAINT uq_conversations_id_site "
        "UNIQUE USING INDEX uq_conversations_id_site"
    )
    op.execute(
        "ALTER TABLE kb_pages ADD CONSTRAINT uq_kb_pages_id_site "
        "UNIQUE USING INDEX uq_kb_pages_id_site"
    )
    op.drop_constraint(
        "handoff_contexts_conversation_id_fkey", "handoff_contexts", type_="foreignkey"
    )
    op.drop_constraint("handoff_contexts_snapshot_id_fkey", "handoff_contexts", type_="foreignkey")
    op.drop_constraint("messages_conversation_id_fkey", "messages", type_="foreignkey")
    op.drop_constraint("fk_messages_snapshot_id", "messages", type_="foreignkey")
    op.create_foreign_key(
        "fk_kb_pages_source_site",
        "kb_pages",
        "kb_sources",
        ["source_id", "site_id"],
        ["id", "site_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_kb_chunks_page_site",
        "kb_chunks",
        "kb_pages",
        ["page_id", "site_id"],
        ["id", "site_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_handoff_contexts_conversation_site",
        "handoff_contexts",
        "conversations",
        ["conversation_id", "site_id"],
        ["id", "site_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_handoff_contexts_snapshot_site",
        "handoff_contexts",
        "kb_snapshots",
        ["snapshot_id", "site_id"],
        ["id", "site_id"],
        ondelete="SET NULL (snapshot_id)",
    )
    op.add_column("messages", sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE messages AS m
        SET site_id = c.site_id
        FROM conversations AS c
        WHERE c.id = m.conversation_id
        """
    )
    op.alter_column("messages", "site_id", nullable=False)
    op.create_foreign_key(
        "fk_messages_conversation_site",
        "messages",
        "conversations",
        ["conversation_id", "site_id"],
        ["id", "site_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_messages_snapshot_site",
        "messages",
        "kb_snapshots",
        ["snapshot_id", "site_id"],
        ["id", "site_id"],
        ondelete="SET NULL (snapshot_id)",
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_snapshot_site", "messages", type_="foreignkey")
    op.drop_constraint("fk_messages_conversation_site", "messages", type_="foreignkey")
    op.create_foreign_key(
        "messages_conversation_id_fkey",
        "messages",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_messages_snapshot_id",
        "messages",
        "kb_snapshots",
        ["snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("messages", "site_id")
    op.drop_constraint("fk_handoff_contexts_snapshot_site", "handoff_contexts", type_="foreignkey")
    op.drop_constraint(
        "fk_handoff_contexts_conversation_site", "handoff_contexts", type_="foreignkey"
    )
    op.create_foreign_key(
        "handoff_contexts_conversation_id_fkey",
        "handoff_contexts",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "handoff_contexts_snapshot_id_fkey",
        "handoff_contexts",
        "kb_snapshots",
        ["snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("fk_kb_chunks_page_site", "kb_chunks", type_="foreignkey")
    op.drop_constraint("fk_kb_pages_source_site", "kb_pages", type_="foreignkey")
    op.drop_constraint("uq_kb_pages_id_site", "kb_pages", type_="unique")
    op.drop_constraint("uq_conversations_id_site", "conversations", type_="unique")
