"""store crawl4ai markdown on kb_pages for numeric validation

Revision ID: 18kbpagemarkdown
Revises: 17kbchunksitecascade
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "18kbpagemarkdown"
down_revision: str | Sequence[str] | None = "17kbchunksitecascade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("kb_pages", sa.Column("markdown", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_pages", "markdown")
