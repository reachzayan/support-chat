"""kb_hybrid_rag

Revision ID: 09kbhybrid01
Revises: 11be8f4f569e
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "09kbhybrid01"
down_revision: str | Sequence[str] | None = "11be8f4f569e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "sites",
        sa.Column("bot_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "sites",
        sa.Column("human_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_check_constraint(
        "ck_sites_human_requires_bot",
        "sites",
        "human_enabled = false OR bot_enabled = true",
    )
    op.add_column(
        "conversations",
        sa.Column(
            "attention_needed", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "messages",
        sa.Column("source_chunk_ids", postgresql.ARRAY(sa.Uuid()), nullable=True),
    )
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
    op.create_table(
        "kb_sources",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("start_url", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), server_default=sa.text("'list'"), nullable=False),
        sa.Column(
            "seed_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "include_globs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "exclude_globs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("max_depth", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("max_pages", sa.Integer(), server_default=sa.text("80"), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("page_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "embedder_id",
            sa.String(),
            server_default=sa.text("'openai:text-embedding-3-small:1536'"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(), server_default=sa.text("'website'"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("mode IN ('prefix','list')", name="ck_kb_sources_mode"),
        sa.CheckConstraint("max_depth >= 1 AND max_depth <= 5", name="ck_kb_sources_depth"),
        sa.CheckConstraint("max_pages >= 1 AND max_pages <= 200", name="ck_kb_sources_pages"),
        sa.CheckConstraint(
            "status IN ('queued','running','ready','failed')", name="ck_kb_sources_status"
        ),
        sa.CheckConstraint("source_kind IN ('website','legacy_faq')", name="ck_kb_sources_kind"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "start_url", name="uq_kb_sources_site_start_url"),
    )
    op.create_table(
        "kb_pages",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("skip_reason", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["kb_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "url", name="uq_kb_pages_source_url"),
    )
    op.create_index("ix_kb_pages_site_enabled", "kb_pages", ["site_id", "enabled"])
    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("context_prefix", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "search_document",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(heading,'')), 'A') || "
                "setweight(to_tsvector('english', coalesce(context_prefix,'') || ' ' "
                "|| coalesce(body,'')), 'B')",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["kb_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_chunks_site_enabled", "kb_chunks", ["site_id", "enabled"])
    op.execute("CREATE INDEX ix_kb_chunks_search ON kb_chunks USING gin (search_document)")
    op.execute(
        "CREATE INDEX ix_kb_chunks_embedding_hnsw ON kb_chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        """
        INSERT INTO kb_sources (site_id, start_url, mode, seed_urls, status, page_count, source_kind, enabled)
        SELECT DISTINCT ON (a.site_id)
            a.site_id,
            'https://legacy.local/faq',
            'list',
            '[]'::jsonb,
            'ready',
            0,
            'legacy_faq',
            true
        FROM kb_articles a
        """
    )
    op.execute(
        """
        INSERT INTO kb_pages (source_id, site_id, url, title, content_text, content_sha256, http_status, enabled)
        SELECT
            s.id,
            a.site_id,
            'https://legacy.local/faq/' || a.id::text,
            a.title,
            a.body,
            encode(sha256(convert_to(a.body, 'UTF8')), 'hex'),
            200,
            a.enabled
        FROM kb_articles a
        JOIN kb_sources s ON s.site_id = a.site_id AND s.source_kind = 'legacy_faq'
        """
    )
    op.execute(
        """
        INSERT INTO kb_chunks (page_id, site_id, ordinal, heading, body, enabled)
        SELECT p.id, p.site_id, 0, p.title, p.content_text, p.enabled
        FROM kb_pages p
        JOIN kb_sources s ON s.id = p.source_id AND s.source_kind = 'legacy_faq'
        """
    )
    op.execute(
        """
        UPDATE kb_sources s
        SET page_count = (
            SELECT count(*) FROM kb_pages p WHERE p.source_id = s.id
        )
        WHERE s.source_kind = 'legacy_faq'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_kb_chunks_embedding_hnsw", table_name="kb_chunks")
    op.drop_index("ix_kb_chunks_search", table_name="kb_chunks")
    op.drop_table("kb_chunks")
    op.drop_table("kb_pages")
    op.drop_table("kb_sources")
    op.drop_constraint("ck_messages_sources", "messages", type_="check")
    op.create_check_constraint(
        "ck_messages_sources",
        "messages",
        "(role = 'bot' AND source_article_ids IS NOT NULL AND cardinality(source_article_ids) > 0) OR "
        "(role <> 'bot' AND (source_article_ids IS NULL))",
    )
    op.drop_column("messages", "source_chunk_ids")
    op.drop_column("conversations", "attention_needed")
    op.drop_constraint("ck_sites_human_requires_bot", "sites", type_="check")
    op.drop_column("sites", "human_enabled")
    op.drop_column("sites", "bot_enabled")
