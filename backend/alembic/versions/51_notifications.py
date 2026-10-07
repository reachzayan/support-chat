"""Durable per-staff notifications and site/scenario delivery preferences."""

import sqlalchemy as sa

from alembic import op

revision = "51notifications"
down_revision = "50cannedhistory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    scenarios = "scenario IN ('live','bot','needs_attention','visitor_message','closed')"
    op.create_table(
        "notification_preferences",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "site_id", sa.Uuid(), sa.ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("scenario", sa.String(32), primary_key=True),
        sa.Column("in_app", sa.Boolean(), nullable=False),
        sa.CheckConstraint(scenarios, name="ck_notification_preference_scenario"),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("scenario", sa.String(32), nullable=False),
        sa.Column("event_key", sa.String(100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["conversation_id", "site_id"],
            ["conversations.id", "conversations.site_id"],
            ondelete="CASCADE",
            name="fk_notifications_conversation_site",
        ),
        sa.UniqueConstraint("user_id", "event_key", "scenario", name="uq_notifications_event"),
        sa.CheckConstraint(scenarios, name="ck_notifications_scenario"),
    )
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_notifications_user_id_id",
            "notifications",
            ["user_id", "id"],
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_notifications_unread",
            "notifications",
            ["user_id", "id"],
            postgresql_where=sa.text("read_at IS NULL"),
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("notification_preferences")
