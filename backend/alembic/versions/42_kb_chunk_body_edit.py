"""Record the last body edit id on live knowledge chunks.

Revision ID: 42kbchunkbodyedit
Revises: 41durablebackground
Create Date: 2026-09-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "42kbchunkbodyedit"
down_revision: str | Sequence[str] | None = "41durablebackground"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("kb_chunks", sa.Column("last_body_edit_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_chunks", "last_body_edit_id")
