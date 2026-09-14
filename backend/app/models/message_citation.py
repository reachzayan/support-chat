from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.message import Message


class MessageCitation(Base):
    __tablename__ = "message_citations"
    __table_args__ = (
        CheckConstraint(
            "response_start >= 0 AND response_end >= response_start",
            name="ck_message_citations_response_offsets",
        ),
        CheckConstraint(
            "source_start >= 0 AND source_end >= source_start",
            name="ck_message_citations_source_offsets",
        ),
        Index("ix_message_citations_message_id", "message_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE")
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("kb_chunks.id", ondelete="SET NULL"), nullable=True
    )
    snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("kb_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    response_start: Mapped[int] = mapped_column(Integer)
    response_end: Mapped[int] = mapped_column(Integer)
    source_start: Mapped[int] = mapped_column(Integer)
    source_end: Mapped[int] = mapped_column(Integer)
    cited_text: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(Text)
    message: Mapped["Message"] = relationship(back_populates="citations")
