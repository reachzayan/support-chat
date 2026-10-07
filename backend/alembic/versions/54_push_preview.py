"""Persist generated test notification content for durable preview delivery."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "54pushpreview"
down_revision = "53pushpreferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("push_deliveries", sa.Column("preview", JSONB(none_as_null=True), nullable=True))
    op.execute(
        "ALTER TABLE push_deliveries ADD CONSTRAINT ck_push_preview_test_only "
        "CHECK (notification_id IS NULL OR preview IS NULL) NOT VALID"
    )
    op.execute("ALTER TABLE push_deliveries VALIDATE CONSTRAINT ck_push_preview_test_only")


def downgrade() -> None:
    op.drop_constraint("ck_push_preview_test_only", "push_deliveries", type_="check")
    op.drop_column("push_deliveries", "preview")
