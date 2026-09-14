"""Drop the unused Plan-14 trigram retrieval index.

Hybrid search never consumed ``ix_kb_chunks_grounded_trgm``. Leave the
``pg_trgm`` extension installed; dropping extensions is riskier than an
unused extension.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "23dropgroundedtrgm"
down_revision: str | Sequence[str] | None = "22trustedknowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_kb_chunks_grounded_trgm")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_kb_chunks_grounded_trgm ON kb_chunks "
            "USING gin ("
            "lower(coalesce(canonical_question, '') || ' ' || kb_aliases_as_text(aliases) || ' ' "
            "|| coalesce(heading, '') || ' ' || coalesce(topic_label, '')) gin_trgm_ops)"
        )
