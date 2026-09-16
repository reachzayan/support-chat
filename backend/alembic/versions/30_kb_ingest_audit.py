"""Preserve unchanged crawl audits and renderer details.

Revision ID: 30kbingestaudit
Revises: 29contactinfo
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "30kbingestaudit"
down_revision: str | Sequence[str] | None = "29contactinfo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_kb_snapshots_state", "kb_snapshots", type_="check")
    op.create_check_constraint(
        "ck_kb_snapshots_state",
        "kb_snapshots",
        "state IN ('building','validated','live','superseded','failed','unchanged')",
    )
    op.add_column("kb_page_jobs", sa.Column("renderer", sa.String(), nullable=True))
    op.add_column("kb_page_jobs", sa.Column("http_status", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_page_jobs", "http_status")
    op.drop_column("kb_page_jobs", "renderer")
    op.drop_constraint("ck_kb_snapshots_state", "kb_snapshots", type_="check")
    op.create_check_constraint(
        "ck_kb_snapshots_state",
        "kb_snapshots",
        "state IN ('building','validated','live','superseded','failed')",
    )
