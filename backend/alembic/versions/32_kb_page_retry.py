"""Add durable single-page retry requests.

Revision ID: 32kbpageretry
Revises: 31kbingestevents
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "32kbpageretry"
down_revision: str | Sequence[str] | None = "31kbingestevents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kb_sources",
        sa.Column(
            "retry_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("kb_sources", "retry_urls")
