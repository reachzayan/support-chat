"""cascade composite snapshot site fk on kb_chunks

Revision ID: 17kbchunksitecascade
Revises: 16kbchunkcascade
Create Date: 2026-09-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "17kbchunksitecascade"
down_revision: str | Sequence[str] | None = "16kbchunkcascade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
