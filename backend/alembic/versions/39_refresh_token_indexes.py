"""Refresh-token lookup indexes.

Revision ID: 39refreshtokenindexes
Revises: 38tenantcompositefks
Create Date: 2026-09-22

The visitor-history index is created concurrently in revision 37. This revision
only adds refresh-token indexes aligned with revocation filters (revoked_at IS NULL).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "39refreshtokenindexes"
down_revision: str | Sequence[str] | None = "38tenantcompositefks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_refresh_tokens_family_id
        ON refresh_tokens (family_id)
        WHERE revoked_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id
        ON refresh_tokens (user_id)
        WHERE revoked_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_user_id")
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_family_id")
