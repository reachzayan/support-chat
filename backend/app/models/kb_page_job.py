from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KbPageJob(Base):
    __tablename__ = "kb_page_jobs"
    __table_args__ = (
        UniqueConstraint("page_id", "snapshot_id", name="uq_kb_page_jobs_page_snapshot"),
        CheckConstraint(
            "stage IN ('fetch','extract','llm_extract','embed','persist')",
            name="ck_kb_page_jobs_stage",
        ),
        CheckConstraint(
            "state IN ('pending','running','done','transient_failed','dead_letter','unchanged')",
            name="ck_kb_page_jobs_state",
        ),
        Index(
            "ix_kb_page_jobs_ready",
            "next_run_at",
            "id",
            postgresql_where=text("state IN ('pending','transient_failed')"),
        ),
        Index("ix_kb_page_jobs_source_state", "source_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    source_id: Mapped[UUID] = mapped_column(ForeignKey("kb_sources.id", ondelete="CASCADE"))
    page_id: Mapped[UUID] = mapped_column(ForeignKey("kb_pages.id", ondelete="CASCADE"))
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("kb_snapshots.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String, server_default=text("'fetch'"))
    state: Mapped[str] = mapped_column(String, server_default=text("'pending'"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("5"))
    last_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
