from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
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


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (Index("ix_push_subscriptions_user", "user_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_version: Mapped[int] = mapped_column(Integer)
    endpoint: Mapped[str] = mapped_column(String(2048), unique=True)
    p256dh: Mapped[str] = mapped_column(String(100))
    auth: Mapped[str] = mapped_column(String(32))
    silent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PushDelivery(Base):
    __tablename__ = "push_deliveries"
    __table_args__ = (
        CheckConstraint(
            "notification_id IS NULL OR preview IS NULL", name="ck_push_preview_test_only"
        ),
        UniqueConstraint("notification_id", "subscription_id", name="uq_push_delivery_event"),
        Index(
            "ix_push_deliveries_pending",
            "next_attempt_at",
            postgresql_where=text("finished_at IS NULL"),
        ),
        Index("ix_push_deliveries_subscription", "subscription_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    notification_id: Mapped[int | None] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE")
    )
    subscription_id: Mapped[UUID] = mapped_column(
        ForeignKey("push_subscriptions.id", ondelete="CASCADE")
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    preview: Mapped[dict[str, str] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
