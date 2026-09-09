from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

HANDOFF_OUTCOMES = (
    "resolved",
    "callback_completed",
    "no_response",
    "abandoned",
    "duplicate",
)


class HandoffOutcome(Base):
    __tablename__ = "handoff_outcomes"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('resolved','callback_completed','no_response','abandoned','duplicate')",
            name="ck_handoff_outcomes_outcome",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    handoff_id: Mapped[UUID] = mapped_column(
        ForeignKey("handoff_contexts.id", ondelete="CASCADE"), unique=True
    )
    resolved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    outcome: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
