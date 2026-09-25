from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

INQUIRY_TYPES = ("sales", "results", "portal", "compliance", "other")
INTENTS = ("pricing", "turnaround", "dot", "fcra", "portal", "escalate", "other")
STATES = ("prechat", "bot", "queued", "human", "closed")
ESCALATION_REASONS = (
    "visitor_request",
    "sensitive",
    "individual_case",
    "retrieval_miss",
    "sufficiency_fail",
    "provider_timeout",
    "repeated_miss",
    "policy_boundary",
    "rate_ceiling",
    "off_topic",
)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("id", "site_id", name="uq_conversations_id_site"),
        ForeignKeyConstraint(
            ["visitor_id", "site_id"],
            ["visitors.id", "visitors.site_id"],
            name="fk_conversations_visitor_site",
        ),
        CheckConstraint(
            "state IN ('prechat','bot','queued','human','closed')", name="ck_conversations_state"
        ),
        CheckConstraint("fallback_count >= 0", name="ck_conversations_fallback"),
        CheckConstraint(
            "inquiry_type IS NULL OR inquiry_type IN ('sales','results','portal','compliance','other')",
            name="ck_conversations_inquiry",
        ),
        CheckConstraint(
            "intent IS NULL OR intent IN ('pricing','turnaround','dot','fcra','portal','escalate','other')",
            name="ck_conversations_intent",
        ),
        CheckConstraint(
            "(active_generation_id IS NULL) OR (state = 'bot')",
            name="ck_conversations_generation_bot_only",
        ),
        CheckConstraint(
            "(state = 'human' AND assigned_agent_id IS NOT NULL) OR "
            "(state IN ('prechat','bot','queued') AND assigned_agent_id IS NULL) OR "
            "(state = 'closed')",
            name="ck_conversations_assignment",
        ),
        CheckConstraint(
            "escalation_reason IS NULL OR escalation_reason IN ("
            + ", ".join(f"'{item}'" for item in ESCALATION_REASONS)
            + ")",
            name="conversations_escalation_reason_check",
        ),
        Index(
            "uq_conversations_open_visitor",
            "visitor_id",
            unique=True,
            postgresql_where=text("state <> 'closed'"),
        ),
        Index("ix_conversations_site_last_message", "site_id", "last_message_at"),
        Index("ix_conversations_state_last_message", "state", "last_message_at"),
        Index(
            "ix_conversations_visitor_site_last_message", "visitor_id", "site_id", "last_message_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    visitor_id: Mapped[UUID]
    state: Mapped[str] = mapped_column(String)
    active_generation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    generation_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    generation_lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    prechat_submission_id: Mapped[UUID | None] = mapped_column(nullable=True)
    prechat_payload_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    inquiry_type: Mapped[str | None] = mapped_column(String, nullable=True)
    intent: Mapped[str | None] = mapped_column(String, nullable=True)
    fallback_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    page_url: Mapped[str | None] = mapped_column(String, nullable=True)
    page_title: Mapped[str | None] = mapped_column(String, nullable=True)
    referrer: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    attention_needed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    escalation_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
