"""LiveChat canned fields: aliases, import id, suggestion event, bot flag.

Revision ID: 44cannedlivechat
Revises: 43visitorblocks
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "44cannedlivechat"
down_revision: str | Sequence[str] | None = "43visitorblocks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "canned_replies",
        sa.Column("external_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "canned_replies",
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::character varying[]"),
        ),
    )
    op.add_column(
        "canned_replies",
        sa.Column("suggestion_event", sa.String(), nullable=True),
    )
    op.add_column(
        "canned_replies",
        sa.Column(
            "bot_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_check_constraint(
        "ck_canned_replies_suggestion_event",
        "canned_replies",
        "suggestion_event IS NULL OR suggestion_event IN "
        "('start_chat','idle','good_rate','bad_rate','transfer')",
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE canned_replies VALIDATE CONSTRAINT ck_canned_replies_suggestion_event")
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE UNIQUE INDEX CONCURRENTLY uq_canned_replies_external_id
            ON canned_replies (external_id)
            WHERE external_id IS NOT NULL
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS uq_canned_replies_external_id")
    op.drop_constraint("ck_canned_replies_suggestion_event", "canned_replies", type_="check")
    op.drop_column("canned_replies", "bot_eligible")
    op.drop_column("canned_replies", "suggestion_event")
    op.drop_column("canned_replies", "aliases")
    op.drop_column("canned_replies", "external_id")
