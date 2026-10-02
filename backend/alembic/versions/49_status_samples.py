"""Create Date: 2026-10-02

Revision ID: 49statussamples
Revises: 48knowledgegapnote
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "49statussamples"
down_revision: str | Sequence[str] | None = "48knowledgegapnote"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "status_samples",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "service IN ('api', 'postgres', 'redis', 'worker')",
            name="ck_status_samples_service",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_status_samples_created_at", "status_samples", ["created_at"])
    op.create_index(
        "ix_status_samples_service_created_at", "status_samples", ["service", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_status_samples_service_created_at", table_name="status_samples")
    op.drop_index("ix_status_samples_created_at", table_name="status_samples")
    op.drop_table("status_samples")
