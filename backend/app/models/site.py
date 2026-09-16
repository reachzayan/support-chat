from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = (
        CheckConstraint(
            "human_enabled = false OR bot_enabled = true",
            name="ck_sites_human_requires_bot",
        ),
        CheckConstraint(
            "callback_window_hours >= 1 AND callback_window_hours <= 168",
            name="ck_sites_callback_window_hours",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    key: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    public_key: Mapped[str] = mapped_column(String, unique=True)
    allowed_origins: Mapped[list[str]] = mapped_column(JSONB)
    greeting: Mapped[str] = mapped_column(String)
    privacy_url: Mapped[str] = mapped_column(String)
    website_url: Mapped[str | None] = mapped_column(String, nullable=True)
    widget_installed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    widget_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    bot_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    human_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    callback_window_hours: Mapped[int] = mapped_column(
        Integer, server_default=text("24"), nullable=False
    )
    off_brand_blocklist: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
    contact_info: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
