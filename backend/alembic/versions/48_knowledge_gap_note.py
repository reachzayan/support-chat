"""Add a note for the website team to knowledge_gaps.

Revision ID: 48knowledgegapnote
Revises: 47cannedcontext
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "48knowledgegapnote"
down_revision: str | Sequence[str] | None = "47cannedcontext"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_gaps", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_gaps", "note")
