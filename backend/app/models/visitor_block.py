from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VisitorBlock(Base):
    __tablename__ = "visitor_blocks"
    __table_args__ = (
        CheckConstraint(
            "ip IS NOT NULL OR email IS NOT NULL OR phone IS NOT NULL",
            name="ck_visitor_blocks_identifier",
        ),
        Index("ix_visitor_blocks_site_ip", "site_id", "ip"),
        Index("ix_visitor_blocks_site_email", "site_id", "email"),
        Index("ix_visitor_blocks_site_phone", "site_id", "phone"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
