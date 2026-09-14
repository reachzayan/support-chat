"""Make grounded response handling mandatory for every site.

Revision ID: 21unconditionalgrounded
Revises: 20groundedv2
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "21unconditionalgrounded"
down_revision: str | Sequence[str] | None = "20groundedv2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("sites", "grounded_outcomes_v2")


def downgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "grounded_outcomes_v2",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
