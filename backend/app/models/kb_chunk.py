from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

EMBEDDING_DIM = 1536

SEARCH_DOCUMENT_SQL = (
    "setweight(to_tsvector('english', coalesce(canonical_question, '')), 'A') || "
    "setweight(to_tsvector('english', kb_aliases_as_text(aliases)), 'A') || "
    "setweight(to_tsvector('english', coalesce(heading, '')), 'B') || "
    "setweight(to_tsvector('english', coalesce(body, '')), 'C')"
)


class KbChunk(Base):
    __tablename__ = "kb_chunks"
    __table_args__ = (
        Index("ix_kb_chunks_site_enabled", "site_id", "enabled"),
        CheckConstraint(
            "kind IN ('faq','section','table','definition','prose','refusal','fact')",
            name="ck_kb_chunks_kind",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "site_id"],
            ["kb_snapshots.id", "kb_snapshots.site_id"],
            name="fk_kb_chunks_snapshot_site",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    page_id: Mapped[UUID] = mapped_column(ForeignKey("kb_pages.id", ondelete="CASCADE"))
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("kb_snapshots.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String, server_default=text("'prose'"))
    heading: Mapped[str] = mapped_column(String)
    canonical_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_verbatim: Mapped[str] = mapped_column(Text)
    aliases: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    # Kept as compatibility metadata for rows written by revision 20.  It is
    # not a publication gate; site-owned ingestion is trusted immediately.
    approved: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    review_status: Mapped[str] = mapped_column(
        String, server_default=text("'approved'"), nullable=False
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String, server_default=text("''"), nullable=False)
    risk_class: Mapped[str] = mapped_column(
        String, server_default=text("'general'"), nullable=False
    )
    answer_mode: Mapped[str] = mapped_column(
        String, server_default=text("'paraphrase_allowed'"), nullable=False
    )
    topic_label: Mapped[str | None] = mapped_column(String, nullable=True)
    requires_human: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    legal_sensitive: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    display_locator: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_urls: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    body: Mapped[str] = mapped_column(Text)
    context_prefix: Mapped[str] = mapped_column(Text, server_default=text("''"))
    search_document: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(SEARCH_DOCUMENT_SQL, persisted=True),
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
