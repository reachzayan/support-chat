"""Add plain-text knowledge sources and explicit citation URLs.

Revision ID: 33kbtextsources
Revises: 32kbpageretry
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "33kbtextsources"
down_revision: str | Sequence[str] | None = "32kbpageretry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("kb_sources", sa.Column("display_name", sa.String(), nullable=True))
    op.add_column("kb_sources", sa.Column("manual_text", sa.Text(), nullable=True))
    op.add_column("kb_pages", sa.Column("citation_url", sa.String(), nullable=True))
    op.execute("UPDATE kb_pages SET citation_url = url")
    op.drop_constraint("ck_kb_sources_kind", "kb_sources", type_="check")
    op.execute(
        "ALTER TABLE kb_sources ADD CONSTRAINT ck_kb_sources_kind "
        "CHECK (source_kind IN ('website','legacy_faq','policy','text')) NOT VALID"
    )
    op.execute("ALTER TABLE kb_sources VALIDATE CONSTRAINT ck_kb_sources_kind")


def downgrade() -> None:
    op.execute("DELETE FROM kb_sources WHERE source_kind = 'text'")
    op.drop_constraint("ck_kb_sources_kind", "kb_sources", type_="check")
    op.create_check_constraint(
        "ck_kb_sources_kind",
        "kb_sources",
        "source_kind IN ('website','legacy_faq','policy')",
    )
    op.drop_column("kb_pages", "citation_url")
    op.drop_column("kb_sources", "manual_text")
    op.drop_column("kb_sources", "display_name")
