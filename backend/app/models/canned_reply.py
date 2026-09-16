from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CannedReply(Base):
    __tablename__ = "canned_replies"
    __table_args__ = (
        Index(
            "uq_canned_replies_general_shortcut_lower",
            text("lower(shortcut)"),
            unique=True,
            postgresql_where=text("site_id IS NULL"),
        ),
        Index(
            "uq_canned_replies_site_shortcut_lower",
            "site_id",
            text("lower(shortcut)"),
            unique=True,
            postgresql_where=text("site_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    site_id: Mapped[UUID | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    shortcut: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
