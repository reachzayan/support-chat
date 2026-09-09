"""Add sites.off_brand_blocklist and allow policy sources for refusals.

Revision ID: 12offbrand01
Revises: 11asysreason1
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "12offbrand01"
down_revision: str | Sequence[str] | None = "11asysreason1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "off_brand_blocklist",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.drop_constraint("ck_kb_sources_kind", "kb_sources", type_="check")
    op.create_check_constraint(
        "ck_kb_sources_kind",
        "kb_sources",
        "source_kind IN ('website','legacy_faq','policy')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_kb_sources_kind", "kb_sources", type_="check")
    op.create_check_constraint(
        "ck_kb_sources_kind",
        "kb_sources",
        "source_kind IN ('website','legacy_faq')",
    )
    op.drop_column("sites", "off_brand_blocklist")
