"""Tenant-scope message citations and source_chunk_ids.

Revision ID: 40citationtenantfks
Revises: 39refreshtokenindexes
Create Date: 2026-09-22
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "40citationtenantfks"
down_revision: str | Sequence[str] | None = "39refreshtokenindexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GENERAL_TAB_KEY = "supportchat.kb.general."


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "uq_messages_id_site",
            "messages",
            ["id", "site_id"],
            unique=True,
            postgresql_concurrently=True,
        )
        op.create_index(
            "uq_kb_chunks_id_site",
            "kb_chunks",
            ["id", "site_id"],
            unique=True,
            postgresql_concurrently=True,
        )
    op.execute(
        "ALTER TABLE messages ADD CONSTRAINT uq_messages_id_site "
        "UNIQUE USING INDEX uq_messages_id_site"
    )
    op.execute(
        "ALTER TABLE kb_chunks ADD CONSTRAINT uq_kb_chunks_id_site "
        "UNIQUE USING INDEX uq_kb_chunks_id_site"
    )
    op.add_column(
        "message_citations",
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE message_citations AS c
        SET site_id = m.site_id
        FROM messages AS m
        WHERE m.id = c.message_id
        """
    )
    op.alter_column("message_citations", "site_id", nullable=False)
    op.drop_constraint("message_citations_message_id_fkey", "message_citations", type_="foreignkey")
    op.drop_constraint("message_citations_chunk_id_fkey", "message_citations", type_="foreignkey")
    op.drop_constraint(
        "message_citations_snapshot_id_fkey", "message_citations", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_message_citations_message_site",
        "message_citations",
        "messages",
        ["message_id", "site_id"],
        ["id", "site_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_message_citations_chunk_site",
        "message_citations",
        "kb_chunks",
        ["chunk_id", "site_id"],
        ["id", "site_id"],
        ondelete="SET NULL (chunk_id)",
    )
    op.create_foreign_key(
        "fk_message_citations_snapshot_site",
        "message_citations",
        "kb_snapshots",
        ["snapshot_id", "site_id"],
        ["id", "site_id"],
        ondelete="SET NULL (snapshot_id)",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION messages_source_chunks_same_site()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.source_chunk_ids IS NULL THEN
                RETURN NEW;
            END IF;
            IF EXISTS (
                SELECT 1
                FROM unnest(NEW.source_chunk_ids) AS chunk_id(id)
                LEFT JOIN kb_chunks AS c
                    ON c.id = chunk_id.id AND c.site_id = NEW.site_id
                WHERE c.id IS NULL
            ) THEN
                RAISE EXCEPTION 'source_chunk_ids must reference same-site kb_chunks'
                    USING ERRCODE = '23503';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_messages_source_chunks_same_site
        BEFORE INSERT OR UPDATE OF source_chunk_ids, site_id
        ON messages
        FOR EACH ROW
        EXECUTE PROCEDURE messages_source_chunks_same_site();
        """
    )
    op.add_column(
        "kb_sources",
        sa.Column("general_tab_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM kb_sources")).fetchall()
    for (source_id,) in rows:
        tab_id = uuid5(NAMESPACE_URL, f"{GENERAL_TAB_KEY}{source_id}")
        bind.execute(
            sa.text("UPDATE kb_sources SET general_tab_id = :tab WHERE id = :id"),
            {"tab": tab_id, "id": source_id},
        )
    op.alter_column("kb_sources", "general_tab_id", nullable=False)
    with op.get_context().autocommit_block():
        op.create_index(
            "uq_kb_sources_general_tab_id",
            "kb_sources",
            ["general_tab_id"],
            unique=True,
            postgresql_concurrently=True,
        )
    op.execute(
        "ALTER TABLE kb_sources ADD CONSTRAINT uq_kb_sources_general_tab_id "
        "UNIQUE USING INDEX uq_kb_sources_general_tab_id"
    )


def downgrade() -> None:
    op.drop_constraint("uq_kb_sources_general_tab_id", "kb_sources", type_="unique")
    op.drop_column("kb_sources", "general_tab_id")
    op.execute("DROP TRIGGER IF EXISTS trg_messages_source_chunks_same_site ON messages")
    op.execute("DROP FUNCTION IF EXISTS messages_source_chunks_same_site()")
    op.drop_constraint(
        "fk_message_citations_snapshot_site", "message_citations", type_="foreignkey"
    )
    op.drop_constraint("fk_message_citations_chunk_site", "message_citations", type_="foreignkey")
    op.drop_constraint("fk_message_citations_message_site", "message_citations", type_="foreignkey")
    op.create_foreign_key(
        "message_citations_message_id_fkey",
        "message_citations",
        "messages",
        ["message_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "message_citations_chunk_id_fkey",
        "message_citations",
        "kb_chunks",
        ["chunk_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "message_citations_snapshot_id_fkey",
        "message_citations",
        "kb_snapshots",
        ["snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("message_citations", "site_id")
    op.drop_constraint("uq_kb_chunks_id_site", "kb_chunks", type_="unique")
    op.drop_constraint("uq_messages_id_site", "messages", type_="unique")
