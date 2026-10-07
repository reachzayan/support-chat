"""Accent-folded, indexed workspace search without an external search service."""

from alembic import op

revision = "56workspacesearch"
down_revision = "55handoffwait"
branch_labels = None
depends_on = None

INDEXES = {
    "messages": "body",
    "canned_replies": "coalesce(shortcut, '') || ' ' || canned_aliases_as_text(aliases) || ' ' || coalesce(body, '')",
    "kb_pages": "coalesce(title, '') || ' ' || coalesce(url, '') || ' ' || coalesce(content_text, '')",
    "kb_sources": "coalesce(display_name, '') || ' ' || coalesce(start_url, '')",
    "kb_chunks": "coalesce(canonical_question, '') || ' ' || coalesce(heading, '') || ' ' || coalesce(body, '')",
    "sites": "coalesce(name, '') || ' ' || coalesce(key, '') || ' ' || coalesce(website_url, '')",
    "visitors": "coalesce(name, '') || ' ' || coalesce(email, '') || ' ' || coalesce(phone, '')",
    "knowledge_gaps": "coalesce(question, '') || ' ' || coalesce(note, '')",
    "app_logs": "coalesce(event, '') || ' ' || coalesce(message, '') || ' ' || coalesce(source, '') || ' ' || coalesce(level, '')",
}


def upgrade() -> None:
    # normalize() is built into the supported UTF-8 PostgreSQL runtime. The function
    # is immutable so substring/prefix queries can use pg_trgm expression indexes.
    op.execute(r"""CREATE FUNCTION workspace_search_fold(value text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
        SELECT lower(regexp_replace(normalize(coalesce(value, ''), NFKD), U&'[\0300-\036f]', '', 'g'))
        $$""")
    for table, expression in INDEXES.items():
        op.execute(
            f"CREATE INDEX ix_{table}_workspace_search ON {table} USING gin (workspace_search_fold({expression}) gin_trgm_ops)"
        )


def downgrade() -> None:
    for table in reversed(INDEXES):
        op.execute(f"DROP INDEX ix_{table}_workspace_search")
    op.execute("DROP FUNCTION workspace_search_fold(text)")
