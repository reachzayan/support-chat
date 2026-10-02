from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

GAP_STATUSES = ("open", "canned", "knowledge", "dismissed")


class KnowledgeGap(Base):
    """One repeated visitor question the assistant could not answer, per website."""

    __tablename__ = "knowledge_gaps"
    __table_args__ = (
        UniqueConstraint("id", "site_id", name="uq_knowledge_gaps_id_site"),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{item}'" for item in GAP_STATUSES) + ")",
            name="ck_knowledge_gaps_status",
        ),
        Index("ix_knowledge_gaps_site_status", "site_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    question: Mapped[str] = mapped_column(Text)
    embedder_id: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    status: Mapped[str] = mapped_column(String, server_default=text("'open'"), default="open")
    # Free text for whoever owns the public website ("add a Get started section").
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeGapHit(Base):
    """One bot miss: the visitor question, in one chat. gap_id is empty until clustered."""

    __tablename__ = "knowledge_gap_hits"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "site_id"],
            ["conversations.id", "conversations.site_id"],
            name="fk_knowledge_gap_hits_conversation_site",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["message_id", "site_id"],
            ["messages.id", "messages.site_id"],
            name="fk_knowledge_gap_hits_message_site",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["gap_id", "site_id"],
            ["knowledge_gaps.id", "knowledge_gaps.site_id"],
            name="fk_knowledge_gap_hits_gap_site",
            ondelete="CASCADE",
        ),
        UniqueConstraint("message_id", name="uq_knowledge_gap_hits_message"),
        Index("ix_knowledge_gap_hits_gap_created", "gap_id", "created_at"),
        Index("ix_knowledge_gap_hits_pending", "id", postgresql_where=text("gap_id IS NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    gap_id: Mapped[UUID | None] = mapped_column(nullable=True)
    conversation_id: Mapped[UUID] = mapped_column()
    message_id: Mapped[int] = mapped_column(BigInteger)
    question: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
