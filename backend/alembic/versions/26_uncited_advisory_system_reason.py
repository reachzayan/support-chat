"""Allow uncited_advisory as a citation-free bot system_reason."""

from collections.abc import Sequence

from alembic import op

revision: str = "26uncitedadvisory"
down_revision: str | Sequence[str] | None = "25groundedtrgm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SYSTEM_REASONS = (
    "answer",
    "clarify",
    "escalate",
    "tech_fail",
    "policy_boundary",
    "out_of_scope",
    "insufficient",
    "sensitive",
    "visitor_request",
    "individual_case",
    "retrieval_miss",
    "sufficiency_fail",
    "provider_timeout",
    "repeated_miss",
    "rate_ceiling",
    "off_topic",
    "uncited_advisory",
)

_SOURCE_FREE_REASONS = (
    "clarify",
    "insufficient",
    "tech_fail",
    "policy_boundary",
    "off_topic",
    "out_of_scope",
    "sensitive",
    "uncited_advisory",
)


def upgrade() -> None:
    op.drop_constraint("ck_messages_system_reason", "messages", type_="check")
    system_allowed = ", ".join(f"'{item}'" for item in _SYSTEM_REASONS)
    op.create_check_constraint(
        "ck_messages_system_reason",
        "messages",
        f"system_reason IS NULL OR system_reason IN ({system_allowed})",
    )
    op.drop_constraint("ck_messages_sources", "messages", type_="check")
    source_free = ", ".join(f"'{item}'" for item in _SOURCE_FREE_REASONS)
    op.create_check_constraint(
        "ck_messages_sources",
        "messages",
        "("
        "role = 'bot' AND ("
        "(source_article_ids IS NOT NULL AND cardinality(source_article_ids) > 0) OR "
        "(source_chunk_ids IS NOT NULL AND cardinality(source_chunk_ids) > 0) OR "
        f"system_reason IN ({source_free})"
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
    op.drop_constraint("ck_messages_system_reason", "messages", type_="check")
    legacy = tuple(item for item in _SYSTEM_REASONS if item != "uncited_advisory")
    system_allowed = ", ".join(f"'{item}'" for item in legacy)
    op.create_check_constraint(
        "ck_messages_system_reason",
        "messages",
        f"system_reason IS NULL OR system_reason IN ({system_allowed})",
    )
