"""Keep completed canned CSV uploads and immutable row snapshots."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "50cannedhistory"
down_revision = "49statussamples"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canned_imports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "uploaded_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("uploaded_by_name", sa.String(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("raw_csv", sa.LargeBinary(), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
    )
    op.create_table(
        "canned_import_rows",
        sa.Column(
            "import_id",
            sa.BigInteger(),
            sa.ForeignKey("canned_imports.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("row_number", sa.Integer(), primary_key=True),
        sa.Column(
            "reply_id",
            sa.Uuid(),
            sa.ForeignKey("canned_replies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("canned_import_rows")
    op.drop_table("canned_imports")
