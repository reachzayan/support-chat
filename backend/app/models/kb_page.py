from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KbPage(Base):
    __tablename__ = "kb_pages"
    __table_args__ = (
        UniqueConstraint("id", "site_id", name="uq_kb_pages_id_site"),
        ForeignKeyConstraint(
            ["source_id", "site_id"],
            ["kb_sources.id", "kb_sources.site_id"],
            name="fk_kb_pages_source_site",
            ondelete="CASCADE",
        ),
        Index("uq_kb_pages_source_url", "source_id", "url", unique=True),
        Index("uq_kb_pages_site_url", "site_id", "url", unique=True),
        Index("ix_kb_pages_site_enabled", "site_id", "enabled"),
        CheckConstraint(
            "processing_status IN ("
            "'pending','fetching','fetched','extracting','llm_extracting',"
            "'embedding','ready','failed','unchanged'"
            ")",
            name="ck_kb_pages_processing_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    source_id: Mapped[UUID] = mapped_column(ForeignKey("kb_sources.id", ondelete="CASCADE"))
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    url: Mapped[str] = mapped_column(String)
    citation_url: Mapped[str | None] = mapped_column(String, nullable=True)
    display_locator: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    content_text: Mapped[str] = mapped_column(Text)
    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_sha256: Mapped[str] = mapped_column(String)
    http_status: Mapped[int] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    skip_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    processing_status: Mapped[str] = mapped_column(String, server_default=text("'pending'"))
    markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    @property
    def public_url(self) -> str:
        if self.citation_url is not None:
            return self.citation_url
        return "" if self.url.startswith("kb-text://") else self.url
