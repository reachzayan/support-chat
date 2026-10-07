"""Separate site/scenario push choices from in-app notification preferences."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision = "53pushpreferences"
down_revision = "52webpush"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications", sa.Column("in_app", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.create_table(
        "notification_push_preferences",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "site_id", sa.Uuid(), sa.ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("scenarios", ARRAY(sa.String(32)), nullable=False),
        sa.CheckConstraint(
            "scenarios <@ ARRAY['live','bot','needs_attention','visitor_message','closed']::varchar[]",
            name="ck_notification_push_scenarios",
        ),
    )
    # Preserve existing push choices, which previously followed the in-app preferences.
    op.execute("""
        INSERT INTO notification_push_preferences (user_id, site_id, enabled, scenarios)
        SELECT pairs.user_id, pairs.site_id, true, ARRAY(
            SELECT defaults.scenario
            FROM (VALUES ('live', true), ('bot', false), ('needs_attention', true),
                         ('visitor_message', true), ('closed', false)) AS defaults(scenario, enabled)
            LEFT JOIN notification_preferences AS prefs
              ON prefs.user_id = pairs.user_id AND prefs.site_id = pairs.site_id
             AND prefs.scenario = defaults.scenario
            WHERE coalesce(prefs.in_app, defaults.enabled)
        )::varchar(32)[]
        FROM (SELECT DISTINCT user_id, site_id FROM notification_preferences) AS pairs
    """)


def downgrade() -> None:
    op.drop_table("notification_push_preferences")
    op.drop_column("notifications", "in_app")
