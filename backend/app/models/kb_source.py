from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Schema default only. Runtime sources use configured_embedder_id() from settings.
DEFAULT_EMBEDDER_ID = "openai:text-embedding-3-small:1536"


class KbSource(Base):
    __tablename__ = "kb_sources"
    __table_args__ = (
        UniqueConstraint("id", "site_id", name="uq_kb_sources_id_site"),
        UniqueConstraint("site_id", "start_url", name="uq_kb_sources_site_start_url"),
        CheckConstraint("mode IN ('prefix','list')", name="ck_kb_sources_mode"),
        CheckConstraint("max_depth >= 1 AND max_depth <= 5", name="ck_kb_sources_depth"),
        CheckConstraint("max_pages >= 1 AND max_pages <= 200", name="ck_kb_sources_pages"),
        CheckConstraint(
            "status IN ('queued','running','ready','failed')", name="ck_kb_sources_status"
        ),
        CheckConstraint(
            "stage IN ('idle','discovering','processing','validating','promoting','ready','failed')",
            name="ck_kb_sources_stage",
        ),
        CheckConstraint(
            "source_kind IN ('website','legacy_faq','policy')", name="ck_kb_sources_kind"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    start_url: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String, server_default=text("'list'"))
    seed_urls: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    retry_urls: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    include_globs: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    exclude_globs: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    max_depth: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    max_pages: Mapped[int] = mapped_column(Integer, server_default=text("80"))
    status: Mapped[str] = mapped_column(String, server_default=text("'queued'"))
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    stage: Mapped[str] = mapped_column(String, server_default=text("'idle'"))
    pages_discovered: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    pages_fetched: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    pages_extracted: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    pages_embedded: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    pages_failed: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    pages_skipped_unchanged: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_run_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_run_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    embedder_id: Mapped[str] = mapped_column(
        String, server_default=text(f"'{DEFAULT_EMBEDDER_ID}'")
    )
    source_kind: Mapped[str] = mapped_column(String, server_default=text("'website'"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
