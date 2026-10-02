"""Probe samples for the staff status board (no transcript or connection strings)."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

STATUS_SERVICES = ("api", "postgres", "redis", "worker")


class StatusSample(Base):
    __tablename__ = "status_samples"
    __table_args__ = (
        CheckConstraint(
            "service IN (" + ", ".join(f"'{item}'" for item in STATUS_SERVICES) + ")",
            name="ck_status_samples_service",
        ),
        Index("ix_status_samples_service_created_at", "service", "created_at"),
        Index("ix_status_samples_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
