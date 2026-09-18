"""Record which pages a shared knowledge answer originally appeared on.

Revision ID: 34kbchunkorigins
Revises: 33kbtextsources
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "34kbchunkorigins"
down_revision: str | Sequence[str] | None = "33kbtextsources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kb_chunks",
        sa.Column(
            "origin_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("kb_chunks", "origin_urls")
