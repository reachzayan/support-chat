"""kb ingest state machine, page jobs, and llm extract cache

Revision ID: 15kbingestjobs
Revises: 14siteenabled
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "15kbingestjobs"
down_revision: str | Sequence[str] | None = "14siteenabled"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kb_sources",
        sa.Column("stage", sa.String(), server_default=sa.text("'idle'"), nullable=False),
    )
    op.add_column(
        "kb_sources",
        sa.Column("pages_discovered", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "kb_sources",
        sa.Column("pages_fetched", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "kb_sources",
        sa.Column("pages_extracted", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "kb_sources",
        sa.Column("pages_embedded", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "kb_sources",
        sa.Column("pages_failed", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "kb_sources",
        sa.Column(
            "pages_skipped_unchanged", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
    )
    op.add_column(
        "kb_sources",
        sa.Column("last_run_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "kb_sources",
        sa.Column("last_run_finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("kb_sources", sa.Column("last_error_code", sa.String(), nullable=True))
    op.create_check_constraint(
        "ck_kb_sources_stage",
        "kb_sources",
        "stage IN ('idle','discovering','processing','validating','promoting','ready','failed')",
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE kb_sources VALIDATE CONSTRAINT ck_kb_sources_stage")
    op.execute(
        """
        UPDATE kb_sources SET stage = CASE
            WHEN status = 'running' THEN 'processing'
            WHEN status = 'failed' THEN 'failed'
            WHEN status = 'ready' THEN 'ready'
            ELSE 'idle'
        END
        """
    )

    op.add_column(
        "kb_pages",
        sa.Column(
            "processing_status", sa.String(), server_default=sa.text("'pending'"), nullable=False
        ),
    )
    op.add_column(
        "kb_pages",
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "kb_pages",
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("kb_pages", sa.Column("failure_reason", sa.String(), nullable=True))
    op.create_check_constraint(
        "ck_kb_pages_processing_status",
        "kb_pages",
        "processing_status IN ("
        "'pending','fetching','fetched','extracting','llm_extracting',"
        "'embedding','ready','failed','unchanged'"
        ")",
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE kb_pages VALIDATE CONSTRAINT ck_kb_pages_processing_status")
    op.execute(
        """
        UPDATE kb_pages SET processing_status = 'ready'
        WHERE id IN (
            SELECT DISTINCT c.page_id
            FROM kb_chunks c
            JOIN kb_snapshots s ON s.id = c.snapshot_id
            WHERE s.state = 'live'
        )
        """
    )

    op.create_table(
        "kb_page_jobs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(), server_default=sa.text("'fetch'"), nullable=False),
        sa.Column("state", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column("last_error_message", sa.String(), nullable=True),
        sa.Column(
            "next_run_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["kb_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["kb_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["kb_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_id", "snapshot_id", name="uq_kb_page_jobs_page_snapshot"),
        sa.CheckConstraint(
            "stage IN ('fetch','extract','llm_extract','embed','persist')",
            name="ck_kb_page_jobs_stage",
        ),
        sa.CheckConstraint(
            "state IN ('pending','running','done','transient_failed','dead_letter','unchanged')",
            name="ck_kb_page_jobs_state",
        ),
    )
    op.create_index("ix_kb_page_jobs_source_state", "kb_page_jobs", ["source_id", "state"])
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_kb_page_jobs_ready "
            "ON kb_page_jobs (next_run_at, id) "
            "WHERE state IN ('pending','transient_failed')"
        )

    op.create_table(
        "kb_page_llm_extracts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("content_sha256", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["page_id"], ["kb_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "page_id",
            "content_sha256",
            "prompt_version",
            name="uq_kb_page_llm_extracts_page_hash_version",
        ),
    )

    op.drop_constraint("ck_kb_chunks_kind", "kb_chunks", type_="check")
    op.create_check_constraint(
        "ck_kb_chunks_kind",
        "kb_chunks",
        "kind IN ('faq','section','table','definition','prose','refusal','fact')",
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE kb_chunks VALIDATE CONSTRAINT ck_kb_chunks_kind")


def downgrade() -> None:
    op.drop_constraint("ck_kb_chunks_kind", "kb_chunks", type_="check")
    op.create_check_constraint(
        "ck_kb_chunks_kind",
        "kb_chunks",
        "kind IN ('faq','section','table','definition','prose','refusal')",
        postgresql_not_valid=True,
    )
    op.execute("ALTER TABLE kb_chunks VALIDATE CONSTRAINT ck_kb_chunks_kind")
    op.drop_table("kb_page_llm_extracts")
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_kb_page_jobs_ready")
    op.drop_index("ix_kb_page_jobs_source_state", table_name="kb_page_jobs")
    op.drop_table("kb_page_jobs")
    op.drop_constraint("ck_kb_pages_processing_status", "kb_pages", type_="check")
    op.drop_column("kb_pages", "failure_reason")
    op.drop_column("kb_pages", "last_success_at")
    op.drop_column("kb_pages", "first_seen_at")
    op.drop_column("kb_pages", "processing_status")
    op.drop_constraint("ck_kb_sources_stage", "kb_sources", type_="check")
    op.drop_column("kb_sources", "last_error_code")
    op.drop_column("kb_sources", "last_run_finished_at")
    op.drop_column("kb_sources", "last_run_started_at")
    op.drop_column("kb_sources", "pages_skipped_unchanged")
    op.drop_column("kb_sources", "pages_failed")
    op.drop_column("kb_sources", "pages_embedded")
    op.drop_column("kb_sources", "pages_extracted")
    op.drop_column("kb_sources", "pages_fetched")
    op.drop_column("kb_sources", "pages_discovered")
    op.drop_column("kb_sources", "stage")
