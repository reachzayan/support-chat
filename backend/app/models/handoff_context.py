from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

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

PROVIDER_STATUSES = ("ok", "timeout", "error", "rate_limited")
HANDOFF_ROUTES = ("live_queue", "callback")


class HandoffContext(Base):
    __tablename__ = "handoff_contexts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "site_id"],
            ["conversations.id", "conversations.site_id"],
            name="fk_handoff_contexts_conversation_site",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "site_id"],
            ["kb_snapshots.id", "kb_snapshots.site_id"],
            name="fk_handoff_contexts_snapshot_site",
            ondelete="SET NULL (snapshot_id)",
        ),
        CheckConstraint(
            "escalation_reason IN (" + ", ".join(f"'{item}'" for item in ESCALATION_REASONS) + ")",
            name="ck_handoff_contexts_reason",
        ),
        CheckConstraint(
            "provider_status IN ('ok','timeout','error','rate_limited')",
            name="ck_handoff_contexts_provider_status",
        ),
        CheckConstraint(
            "route IN ('live_queue','callback')",
            name="ck_handoff_contexts_route",
        ),
        Index(
            "ix_handoff_contexts_conversation_created",
            "conversation_id",
            "created_at",
        ),
        Index(
            "ix_handoff_contexts_site_created",
            "site_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[UUID] = mapped_column()
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    escalation_reason: Mapped[str] = mapped_column(Text)
    original_question: Mapped[str] = mapped_column(Text)
    clarification_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    machine_summary: Mapped[str] = mapped_column(Text, server_default=text("''"))
    machine_summary_model: Mapped[str] = mapped_column(Text, server_default=text("''"))
    candidate_unit_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), server_default=text("'{}'::uuid[]")
    )
    rejection_reasons: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    provider_stage_timings: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    provider_status: Mapped[str] = mapped_column(String)
    promised_response_by: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    route: Mapped[str] = mapped_column(String)
    snapshot_id: Mapped[UUID | None] = mapped_column(nullable=True)
