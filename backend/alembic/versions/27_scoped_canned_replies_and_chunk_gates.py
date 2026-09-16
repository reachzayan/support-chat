"""Add scoped canned replies and preserve independent chunk gates."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "27scopedcannedreplies"
down_revision: str | Sequence[str] | None = "26uncitedadvisory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Stop rather than silently merging distinct staff-authored responses.
    op.execute(
        """
        DO $$
        DECLARE duplicate_scope text;
        DECLARE duplicate_shortcut text;
        BEGIN
          SELECT coalesce(site_id::text, 'General'),
                 lower(regexp_replace(btrim(shortcut), '^#', ''))
          INTO duplicate_scope, duplicate_shortcut
          FROM canned_replies
          GROUP BY site_id, lower(regexp_replace(btrim(shortcut), '^#', ''))
          HAVING count(*) > 1
          LIMIT 1;
          IF FOUND THEN
            RAISE EXCEPTION
              'Cannot normalize canned replies: duplicate shortcut % in scope %',
              duplicate_shortcut, duplicate_scope;
          END IF;
        END $$;
        """
    )
    op.add_column(
        "canned_replies",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.execute("UPDATE canned_replies SET enabled = true")
    op.execute(
        """
        UPDATE canned_replies
        SET shortcut = lower(regexp_replace(btrim(shortcut), '^#', ''))
        """
    )
    op.alter_column("canned_replies", "site_id", nullable=True)
    op.drop_constraint("uq_canned_replies_site_shortcut", "canned_replies", type_="unique")
    # Earlier page-level disabling wrote false to every child. Restore the
    # future independent default while the disabled page remains its parent gate.
    op.execute(
        """
        UPDATE kb_chunks AS chunk
        SET enabled = true
        FROM kb_pages AS page
        WHERE chunk.page_id = page.id AND page.enabled IS FALSE
        """
    )
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE UNIQUE INDEX CONCURRENTLY uq_canned_replies_general_shortcut_lower
            ON canned_replies (lower(shortcut))
            WHERE site_id IS NULL
            """
        )
        op.execute(
            """
            CREATE UNIQUE INDEX CONCURRENTLY uq_canned_replies_site_shortcut_lower
            ON canned_replies (site_id, lower(shortcut))
            WHERE site_id IS NOT NULL
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS uq_canned_replies_site_shortcut_lower")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS uq_canned_replies_general_shortcut_lower")
    has_general = (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS (SELECT 1 FROM canned_replies WHERE site_id IS NULL)"))
        .scalar()
    )
    if has_general:
        raise RuntimeError("Cannot downgrade while General canned replies exist")
    op.create_unique_constraint(
        "uq_canned_replies_site_shortcut", "canned_replies", ["site_id", "shortcut"]
    )
    op.alter_column("canned_replies", "site_id", nullable=False)
    op.drop_column("canned_replies", "enabled")
