from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SCENARIOS = ("live", "bot", "needs_attention", "visitor_message", "closed")
SCENARIO_CHECK = "scenario IN ('live','bot','needs_attention','visitor_message','closed')"
DEFAULT_PUSH_SCENARIOS = ("live", "needs_attention", "visitor_message")


class NotificationPushPreference(Base):
    __tablename__ = "notification_push_preferences"
    __table_args__ = (
        CheckConstraint(
            "scenarios <@ ARRAY['live','bot','needs_attention','visitor_message','closed']::varchar[]",
            name="ck_notification_push_scenarios",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    site_id: Mapped[UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    scenarios: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (CheckConstraint(SCENARIO_CHECK, name="ck_notification_preference_scenario"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    site_id: Mapped[UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
    )
    scenario: Mapped[str] = mapped_column(String(32), primary_key=True)
    in_app: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "site_id"],
            ["conversations.id", "conversations.site_id"],
            ondelete="CASCADE",
            name="fk_notifications_conversation_site",
        ),
        UniqueConstraint("user_id", "event_key", "scenario", name="uq_notifications_event"),
        CheckConstraint(SCENARIO_CHECK, name="ck_notifications_scenario"),
        Index("ix_notifications_user_id_id", "user_id", "id"),
        Index("ix_notifications_unread", "user_id", "id", postgresql_where=text("read_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    site_id: Mapped[UUID]
    conversation_id: Mapped[UUID]
    scenario: Mapped[str] = mapped_column(String(32))
    event_key: Mapped[str] = mapped_column(String(100))
    in_app: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
