"""Create visitor_blocks for site-scoped IP, email, and phone bans.

Revision ID: 43visitorblocks
Revises: 42kbchunkbodyedit
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "43visitorblocks"
down_revision: str | Sequence[str] | None = "42kbchunkbodyedit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visitor_blocks",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ip IS NOT NULL OR email IS NOT NULL OR phone IS NOT NULL",
            name="ck_visitor_blocks_identifier",
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_visitor_blocks_site_ip", "visitor_blocks", ["site_id", "ip"])
    op.create_index("ix_visitor_blocks_site_email", "visitor_blocks", ["site_id", "email"])
    op.create_index("ix_visitor_blocks_site_phone", "visitor_blocks", ["site_id", "phone"])


def downgrade() -> None:
    op.drop_index("ix_visitor_blocks_site_phone", table_name="visitor_blocks")
    op.drop_index("ix_visitor_blocks_site_email", table_name="visitor_blocks")
    op.drop_index("ix_visitor_blocks_site_ip", table_name="visitor_blocks")
    op.drop_table("visitor_blocks")
