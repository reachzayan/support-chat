from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    text,
)
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
        ForeignKeyConstraint(
            ["message_id", "site_id"],
            ["messages.id", "messages.site_id"],
            name="fk_message_citations_message_site",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["chunk_id", "site_id"],
            ["kb_chunks.id", "kb_chunks.site_id"],
            name="fk_message_citations_chunk_site",
            ondelete="SET NULL (chunk_id)",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "site_id"],
            ["kb_snapshots.id", "kb_snapshots.site_id"],
            name="fk_message_citations_snapshot_site",
            ondelete="SET NULL (snapshot_id)",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    message_id: Mapped[int] = mapped_column(BigInteger)
    site_id: Mapped[UUID] = mapped_column()
    chunk_id: Mapped[UUID | None] = mapped_column(nullable=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(nullable=True)
    response_start: Mapped[int] = mapped_column(Integer)
    response_end: Mapped[int] = mapped_column(Integer)
    source_start: Mapped[int] = mapped_column(Integer)
    source_end: Mapped[int] = mapped_column(Integer)
    cited_text: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(Text)
    message: Mapped["Message"] = relationship(back_populates="citations")
