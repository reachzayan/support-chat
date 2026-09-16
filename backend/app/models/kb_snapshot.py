from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KbSnapshot(Base):
    __tablename__ = "kb_snapshots"
    __table_args__ = (
        CheckConstraint(
            "state IN ('building','validated','live','superseded','failed','unchanged')",
            name="ck_kb_snapshots_state",
        ),
        UniqueConstraint("id", "site_id", name="uq_kb_snapshots_id_site"),
        ForeignKeyConstraint(
            ["source_id", "site_id"],
            ["kb_sources.id", "kb_sources.site_id"],
            name="fk_kb_snapshots_source_site",
        ),
        Index(
            "uq_kb_snapshots_live",
            "site_id",
            "source_id",
            unique=True,
            postgresql_where=text("state = 'live'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    source_id: Mapped[UUID] = mapped_column(ForeignKey("kb_sources.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(String, server_default=text("'building'"))
    token_estimate: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    content_hash: Mapped[str] = mapped_column(String, server_default=text("''"))
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    validation_errors: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
