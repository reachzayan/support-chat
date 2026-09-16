"""Add sites.contact_info for bot-shared phone numbers and emails.

Revision ID: 29contactinfo
Revises: 28sitewebsiteurl
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "29contactinfo"
down_revision: str | Sequence[str] | None = "28sitewebsiteurl"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "contact_info",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("sites", "contact_info")
