"""evidence units and snapshots

Revision ID: 10aevidence01
Revises: 09kbhybrid01
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "10aevidence01"
down_revision: str | Sequence[str] | None = "09kbhybrid01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH_DOCUMENT_SQL = (
    "setweight(to_tsvector('english', coalesce(canonical_question, '')), 'A') || "
    "setweight(to_tsvector('english', kb_aliases_as_text(aliases)), 'A') || "
    "setweight(to_tsvector('english', coalesce(heading, '')), 'B') || "
    "setweight(to_tsvector('english', coalesce(body, '')), 'C')"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION kb_aliases_as_text(aliases jsonb)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        AS $$
          SELECT coalesce(string_agg(elem, ' '), '')
          FROM jsonb_array_elements_text(coalesce(aliases, '[]'::jsonb)) AS elem;
        $$
        """
    )
    op.create_index("uq_kb_sources_id_site", "kb_sources", ["id", "site_id"], unique=True)
    op.create_table(
        "kb_snapshots",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(), server_default=sa.text("'building'"), nullable=False),
        sa.Column("token_estimate", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("content_hash", sa.String(), server_default=sa.text("''"), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column(
            "validation_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('building','validated','live','superseded','failed')",
            name="ck_kb_snapshots_state",
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["kb_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_id", "site_id"],
            ["kb_sources.id", "kb_sources.site_id"],
            name="fk_kb_snapshots_source_site",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "site_id", name="uq_kb_snapshots_id_site"),
    )
    op.create_table(
        "kb_smoke_assertions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "must_include",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "must_exclude",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["kb_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("kb_pages", sa.Column("display_locator", sa.String(), nullable=True))
    op.add_column("kb_pages", sa.Column("raw_html", sa.Text(), nullable=True))
    op.add_column("kb_chunks", sa.Column("snapshot_id", sa.Uuid(), nullable=True))
    op.add_column(
        "kb_chunks",
        sa.Column("kind", sa.String(), server_default=sa.text("'prose'"), nullable=False),
    )
    op.add_column("kb_chunks", sa.Column("canonical_question", sa.Text(), nullable=True))
    op.add_column("kb_chunks", sa.Column("answer_verbatim", sa.Text(), nullable=True))
    op.add_column(
        "kb_chunks",
        sa.Column(
            "aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("kb_chunks", sa.Column("topic", sa.String(), nullable=True))
    op.add_column(
        "kb_chunks",
        sa.Column("approved", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "kb_chunks",
        sa.Column("requires_human", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "kb_chunks",
        sa.Column("legal_sensitive", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("kb_chunks", sa.Column("display_locator", sa.String(), nullable=True))
    op.execute(
        """
        INSERT INTO kb_snapshots (site_id, source_id, state, content_hash, token_estimate, promoted_at)
        SELECT s.site_id, s.id, 'live',
               encode(sha256(convert_to(s.id::text, 'UTF8')), 'hex'),
               0, now()
        FROM kb_sources s
        """
    )
    op.execute(
        """
        UPDATE kb_chunks c
        SET snapshot_id = snap.id,
            answer_verbatim = c.body
        FROM kb_pages p
        JOIN kb_snapshots snap
          ON snap.source_id = p.source_id
         AND snap.site_id = p.site_id
         AND snap.state = 'live'
        WHERE c.page_id = p.id
          AND snap.site_id = c.site_id
        """
    )
    op.alter_column("kb_chunks", "snapshot_id", nullable=False)
    op.alter_column("kb_chunks", "answer_verbatim", nullable=False)
    op.create_foreign_key(
        "fk_kb_chunks_snapshot_id", "kb_chunks", "kb_snapshots", ["snapshot_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_kb_chunks_snapshot_site",
        "kb_chunks",
        "kb_snapshots",
        ["snapshot_id", "site_id"],
        ["id", "site_id"],
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE kb_chunks VALIDATE CONSTRAINT fk_kb_chunks_snapshot_site")
    op.create_check_constraint(
        "ck_kb_chunks_kind",
        "kb_chunks",
        "kind IN ('faq','section','table','definition','prose','refusal')",
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE kb_chunks VALIDATE CONSTRAINT ck_kb_chunks_kind")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_search")
    op.execute("ALTER TABLE kb_chunks DROP COLUMN search_document")
    op.execute(
        f"ALTER TABLE kb_chunks ADD COLUMN search_document tsvector "
        f"GENERATED ALWAYS AS ({SEARCH_DOCUMENT_SQL}) STORED"
    )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY ix_kb_chunks_search ON kb_chunks USING gin (search_document)"
        )
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY uq_kb_snapshots_live "
            "ON kb_snapshots (site_id, source_id) WHERE state = 'live'"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS uq_kb_snapshots_live")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_kb_chunks_search")
    op.execute("ALTER TABLE kb_chunks DROP COLUMN search_document")
    op.execute(
        "ALTER TABLE kb_chunks ADD COLUMN search_document tsvector GENERATED ALWAYS AS ("
        "setweight(to_tsvector('english', coalesce(heading,'')), 'A') || "
        "setweight(to_tsvector('english', coalesce(context_prefix,'') || ' ' || coalesce(body,'')), 'B')"
        ") STORED"
    )
    op.execute("CREATE INDEX ix_kb_chunks_search ON kb_chunks USING gin (search_document)")
    op.drop_constraint("ck_kb_chunks_kind", "kb_chunks", type_="check")
    op.drop_constraint("fk_kb_chunks_snapshot_site", "kb_chunks", type_="foreignkey")
    op.drop_constraint("fk_kb_chunks_snapshot_id", "kb_chunks", type_="foreignkey")
    op.drop_column("kb_chunks", "display_locator")
    op.drop_column("kb_chunks", "legal_sensitive")
    op.drop_column("kb_chunks", "requires_human")
    op.drop_column("kb_chunks", "approved")
    op.drop_column("kb_chunks", "topic")
    op.drop_column("kb_chunks", "aliases")
    op.drop_column("kb_chunks", "answer_verbatim")
    op.drop_column("kb_chunks", "canonical_question")
    op.drop_column("kb_chunks", "kind")
    op.drop_column("kb_chunks", "snapshot_id")
    op.drop_column("kb_pages", "raw_html")
    op.drop_column("kb_pages", "display_locator")
    op.drop_table("kb_smoke_assertions")
    op.drop_table("kb_snapshots")
    op.drop_index("uq_kb_sources_id_site", table_name="kb_sources")
    op.execute("DROP FUNCTION IF EXISTS kb_aliases_as_text(jsonb)")
