"""Persisted application logs for admin tracing (no transcript/PII bodies)."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppLog(Base):
    __tablename__ = "app_logs"
    __table_args__ = (
        Index("ix_app_logs_created_at", "created_at"),
        Index("ix_app_logs_level_created_at", "level", "created_at"),
        Index("ix_app_logs_source_created_at", "source", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    logger_name: Mapped[str] = mapped_column(String(128), nullable=False, server_default=text("''"))
    event: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
