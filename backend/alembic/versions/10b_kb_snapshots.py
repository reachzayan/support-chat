"""kb snapshots messages and page canonical unique

Revision ID: 10bksnapshot1
Revises: 10aevidence01
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "10bksnapshot1"
down_revision: str | Sequence[str] | None = "10aevidence01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("snapshot_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_messages_snapshot_id",
        "messages",
        "kb_snapshots",
        ["snapshot_id"],
        ["id"],
        ondelete="SET NULL",
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE messages VALIDATE CONSTRAINT fk_messages_snapshot_id")
    op.execute(
        """
        DELETE FROM kb_chunks
        WHERE page_id IN (
            SELECT p.id FROM kb_pages p
            JOIN kb_pages keep
              ON keep.site_id = p.site_id
             AND keep.url = p.url
             AND keep.fetched_at > p.fetched_at
        )
        """
    )
    op.execute(
        """
        DELETE FROM kb_pages p
        USING kb_pages keep
        WHERE p.site_id = keep.site_id
          AND p.url = keep.url
          AND p.id <> keep.id
          AND keep.fetched_at >= p.fetched_at
          AND keep.id = (
            SELECT k.id FROM kb_pages k
            WHERE k.site_id = p.site_id AND k.url = p.url
            ORDER BY k.fetched_at DESC, k.id DESC
            LIMIT 1
          )
        """
    )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_kb_pages_site_url "
            "ON kb_pages (site_id, url)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS uq_kb_pages_site_url")
    op.drop_constraint("fk_messages_snapshot_id", "messages", type_="foreignkey")
    op.drop_column("messages", "snapshot_id")
