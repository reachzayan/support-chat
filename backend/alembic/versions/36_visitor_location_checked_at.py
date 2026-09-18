"""Track completed visitor IP-location lookups.

Revision ID: 36visitorlocationchecked
Revises: 35visitorlocation
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "36visitorlocationchecked"
down_revision: str | Sequence[str] | None = "35visitorlocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "visitors", sa.Column("location_checked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("visitors", "location_checked_at")
