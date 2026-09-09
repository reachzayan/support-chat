"""sites.callback_window_hours

Revision ID: 13dcallbackwin
Revises: 13chandoffout
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "13dcallbackwin"
down_revision: str | Sequence[str] | None = "13chandoffout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "callback_window_hours",
            sa.Integer(),
            server_default=sa.text("24"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_sites_callback_window_hours",
        "sites",
        "callback_window_hours >= 1 AND callback_window_hours <= 168",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sites_callback_window_hours", "sites", type_="check")
    op.drop_column("sites", "callback_window_hours")
