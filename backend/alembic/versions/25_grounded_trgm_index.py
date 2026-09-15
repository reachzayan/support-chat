"""Recreate the grounded trigram GIN index for lexical-first retrieval."""

from collections.abc import Sequence

from alembic import op

revision: str = "25groundedtrgm"
down_revision: str | Sequence[str] | None = "24botsourcesrelax"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_kb_chunks_grounded_trgm "
            "ON kb_chunks USING gin ("
            "lower("
            "coalesce(canonical_question, '') || ' ' || "
            "kb_aliases_as_text(aliases) || ' ' || "
            "coalesce(heading, '') || ' ' || "
            "coalesce(topic_label, '')"
            ") gin_trgm_ops)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_kb_chunks_grounded_trgm")
