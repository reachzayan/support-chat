from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Visitor(Base):
    __tablename__ = "visitors"
    __table_args__ = (
        UniqueConstraint("id", "site_id", name="uq_visitors_id_site"),
        UniqueConstraint("site_id", "resume_token_hash", name="uq_visitors_site_resume"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    resume_token_hash: Mapped[str] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    geo_country: Mapped[str | None] = mapped_column(String, nullable=True)
    geo_region: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    location_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
