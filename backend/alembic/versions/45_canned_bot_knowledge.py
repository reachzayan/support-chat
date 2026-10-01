"""Index canned replies for bot retrieval and allow citation-free canned replies.

Revision ID: 45cannedbotknowledge
Revises: 44cannedlivechat
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "45cannedbotknowledge"
down_revision: str | Sequence[str] | None = "44cannedlivechat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH_DOCUMENT_SQL = (
    "setweight(to_tsvector('english', coalesce(shortcut, '')), 'A') || "
    "setweight(to_tsvector('english', canned_aliases_as_text(aliases)), 'A') || "
    "setweight(to_tsvector('english', coalesce(body, '')), 'B')"
)

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
    "canned",
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
    "canned",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION canned_aliases_as_text(aliases character varying[])
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        AS $$
          SELECT coalesce(array_to_string(aliases, ' '), '');
        $$
        """
    )
    op.add_column(
        "canned_replies",
        sa.Column("embedder_id", sa.String(), nullable=True),
    )
    op.add_column(
        "canned_replies",
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.add_column(
        "canned_replies",
        sa.Column(
            "search_document",
            postgresql.TSVECTOR(),
            sa.Computed(SEARCH_DOCUMENT_SQL, persisted=True),
        ),
    )
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_canned_replies_search
            ON canned_replies USING gin (search_document)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_canned_replies_bot_scope
            ON canned_replies (site_id)
            WHERE enabled AND bot_eligible
            """
        )

    op.drop_constraint("ck_messages_system_reason", "messages", type_="check")
    system_allowed = ", ".join(f"'{item}'" for item in _SYSTEM_REASONS)
    op.create_check_constraint(
        "ck_messages_system_reason",
        "messages",
        f"system_reason IS NULL OR system_reason IN ({system_allowed})",
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE messages VALIDATE CONSTRAINT ck_messages_system_reason")

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
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE messages VALIDATE CONSTRAINT ck_messages_sources")


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
        "'off_topic','out_of_scope','sensitive','uncited_advisory'"
        ")"
        ")"
        ") OR ("
        "role <> 'bot' AND source_article_ids IS NULL AND source_chunk_ids IS NULL"
        ")",
    )
    op.drop_constraint("ck_messages_system_reason", "messages", type_="check")
    legacy = tuple(item for item in _SYSTEM_REASONS if item != "canned")
    system_allowed = ", ".join(f"'{item}'" for item in legacy)
    op.create_check_constraint(
        "ck_messages_system_reason",
        "messages",
        f"system_reason IS NULL OR system_reason IN ({system_allowed})",
    )
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_canned_replies_bot_scope")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_canned_replies_search")
    op.drop_column("canned_replies", "search_document")
    op.drop_column("canned_replies", "embedding")
    op.drop_column("canned_replies", "embedder_id")
    op.execute("DROP FUNCTION IF EXISTS canned_aliases_as_text(character varying[])")
