"""Allow citation-free bot outcomes for grounded non-answer replies."""

from collections.abc import Sequence

from alembic import op

revision: str = "24botsourcesrelax"
down_revision: str | Sequence[str] | None = "23dropgroundedtrgm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_messages_sources", "messages", type_="check")
    op.create_check_constraint(
        "ck_messages_sources",
        "messages",
        "("
        "role = 'bot' AND ("
        "(source_article_ids IS NOT NULL AND cardinality(source_article_ids) > 0) OR "
        "(source_chunk_ids IS NOT NULL AND cardinality(source_chunk_ids) > 0) OR "
        "system_reason IN ("
        "'clarify','insufficient','tech_fail','policy_boundary',"
        "'off_topic','out_of_scope','sensitive'"
        ")"
        ")"
        ") OR ("
        "role <> 'bot' AND source_article_ids IS NULL AND source_chunk_ids IS NULL"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_messages_sources", "messages", type_="check")
    op.create_check_constraint(
        "ck_messages_sources",
        "messages",
        "(role = 'bot' AND ("
        "(source_article_ids IS NOT NULL AND cardinality(source_article_ids) > 0) OR "
        "(source_chunk_ids IS NOT NULL AND cardinality(source_chunk_ids) > 0)"
        ")) OR "
        "(role <> 'bot' AND source_article_ids IS NULL AND source_chunk_ids IS NULL)",
    )
