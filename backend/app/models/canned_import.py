from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CannedImport(Base):
    __tablename__ = "canned_imports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    uploaded_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_by_name: Mapped[str | None] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String(64))
    raw_csv: Mapped[bytes] = mapped_column(LargeBinary)
    created: Mapped[int] = mapped_column(Integer)
    updated: Mapped[int] = mapped_column(Integer)
    skipped: Mapped[int] = mapped_column(Integer)


class CannedImportRow(Base):
    __tablename__ = "canned_import_rows"

    import_id: Mapped[int] = mapped_column(
        ForeignKey("canned_imports.id", ondelete="CASCADE"), primary_key=True
    )
    row_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    reply_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("canned_replies.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(32))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
