"""cascade kb_chunks when a snapshot is deleted

Revision ID: 16kbchunkcascade
Revises: 15kbingestjobs
Create Date: 2026-09-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "16kbchunkcascade"
down_revision: str | Sequence[str] | None = "15kbingestjobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("fk_kb_chunks_snapshot_id", "kb_chunks", type_="foreignkey")
    op.create_foreign_key(
        "fk_kb_chunks_snapshot_id",
        "kb_chunks",
        "kb_snapshots",
        ["snapshot_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("fk_kb_chunks_snapshot_site", "kb_chunks", type_="foreignkey")
    op.create_foreign_key(
        "fk_kb_chunks_snapshot_site",
        "kb_chunks",
        "kb_snapshots",
        ["snapshot_id", "site_id"],
        ["id", "site_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_kb_chunks_snapshot_site", "kb_chunks", type_="foreignkey")
    op.create_foreign_key(
        "fk_kb_chunks_snapshot_site",
        "kb_chunks",
        "kb_snapshots",
        ["snapshot_id", "site_id"],
        ["id", "site_id"],
    )
    op.drop_constraint("fk_kb_chunks_snapshot_id", "kb_chunks", type_="foreignkey")
    op.create_foreign_key(
        "fk_kb_chunks_snapshot_id",
        "kb_chunks",
        "kb_snapshots",
        ["snapshot_id"],
        ["id"],
    )
