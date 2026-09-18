"""Store the IP-derived visitor location.

Revision ID: 35visitorlocation
Revises: 34kbchunkorigins
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "35visitorlocation"
down_revision: str | Sequence[str] | None = "34kbchunkorigins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("visitors", sa.Column("location", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("visitors", "location")
