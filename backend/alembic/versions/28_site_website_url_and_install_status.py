"""Add site website URL and widget install-detection status."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "28sitewebsiteurl"
down_revision: str | Sequence[str] | None = "27scopedcannedreplies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("website_url", sa.String(), nullable=True))
    op.add_column("sites", sa.Column("widget_installed", sa.Boolean(), nullable=True))
    op.add_column(
        "sites", sa.Column("widget_checked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sites", "widget_checked_at")
    op.drop_column("sites", "widget_installed")
    op.drop_column("sites", "website_url")
