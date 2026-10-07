"""Device subscriptions and durable Web Push delivery queue."""

import sqlalchemy as sa

from alembic import op

revision = "52webpush"
down_revision = "51notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(2048), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(100), nullable=False),
        sa.Column("auth", sa.String(32), nullable=False),
        sa.Column("silent", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "push_deliveries",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "notification_id",
            sa.BigInteger(),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "subscription_id",
            sa.Uuid(),
            sa.ForeignKey("push_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("notification_id", "subscription_id", name="uq_push_delivery_event"),
    )
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_push_subscriptions_user",
            "push_subscriptions",
            ["user_id"],
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_push_deliveries_pending",
            "push_deliveries",
            ["next_attempt_at"],
            postgresql_where=sa.text("finished_at IS NULL"),
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_push_deliveries_subscription",
            "push_deliveries",
            ["subscription_id"],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    op.drop_table("push_deliveries")
    op.drop_table("push_subscriptions")
