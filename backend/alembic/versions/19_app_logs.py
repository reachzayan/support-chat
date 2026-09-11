"""Create Date: 2026-09-11

Revision ID: 19applogs
Revises: 18kbpagemarkdown
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "19applogs"
down_revision: str | Sequence[str] | None = "18kbpagemarkdown"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_logs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "logger_name", sa.String(length=128), server_default=sa.text("''"), nullable=False
        ),
        sa.Column("event", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_logs_created_at", "app_logs", ["created_at"])
    op.create_index("ix_app_logs_level_created_at", "app_logs", ["level", "created_at"])
    op.create_index("ix_app_logs_source_created_at", "app_logs", ["source", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_app_logs_source_created_at", table_name="app_logs")
    op.drop_index("ix_app_logs_level_created_at", table_name="app_logs")
    op.drop_index("ix_app_logs_created_at", table_name="app_logs")
    op.drop_table("app_logs")
