"""Canned replies: 'only after' context, hand-off flag, and corrections to imported rows.

Revision ID: 47cannedcontext
Revises: 46knowledgegaps
Create Date: 2026-10-01

The data statements apply the import rules to rows that were imported before those rules
existed: the DER question chain gets its parents, routing promises get the hand-off flag,
and scripts that claim an agent action or coach visitors to share a licence number are taken
off the bot. They only ever switch the bot OFF; downgrade drops the columns and leaves the
corrected data in place.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "47cannedcontext"
down_revision: str | Sequence[str] | None = "46knowledgegaps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BASE = "regexp_replace(shortcut, '-[0-9]+$', '')"
_DER_FOLLOW_UPS = ("der_yes_followup", "der_no_followup", "der_not_sure_followup")
_HANDS_OFF = ("interpretation", "protected", "dispute-id")
_BOT_OFF = ("verified", "unable-verify", "dispute-logged", "greeting", "driver_identifier_format")


def upgrade() -> None:
    op.add_column("canned_replies", sa.Column("follows_id", sa.Uuid(), nullable=True))
    op.add_column(
        "canned_replies",
        sa.Column("hands_off", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_foreign_key(
        "fk_canned_replies_follows",
        "canned_replies",
        "canned_replies",
        ["follows_id"],
        ["id"],
        ondelete="SET NULL",
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE canned_replies VALIDATE CONSTRAINT fk_canned_replies_follows")

    op.execute(
        sa.text(
            """
            UPDATE canned_replies AS child
            SET follows_id = parent.id
            FROM canned_replies AS parent
            WHERE child.shortcut = ANY(:children)
              AND parent.shortcut = 'der_what_is'
              AND parent.site_id IS NOT DISTINCT FROM child.site_id
            """
        ).bindparams(sa.bindparam("children", list(_DER_FOLLOW_UPS), type_=sa.ARRAY(sa.String)))
    )
    op.execute(
        sa.text(
            f"UPDATE canned_replies SET hands_off = true WHERE {_BASE} = ANY(:slugs)"
        ).bindparams(sa.bindparam("slugs", list(_HANDS_OFF), type_=sa.ARRAY(sa.String)))
    )
    op.execute(
        sa.text(
            f"""
            UPDATE canned_replies
            SET bot_eligible = false, embedding = NULL, embedder_id = NULL
            WHERE bot_eligible
              AND ({_BASE} = ANY(:slugs) OR aliases && CAST(:slugs AS character varying[]))
            """
        ).bindparams(sa.bindparam("slugs", list(_BOT_OFF), type_=sa.ARRAY(sa.String)))
    )


def downgrade() -> None:
    op.drop_constraint("fk_canned_replies_follows", "canned_replies", type_="foreignkey")
    op.drop_column("canned_replies", "hands_off")
    op.drop_column("canned_replies", "follows_id")
