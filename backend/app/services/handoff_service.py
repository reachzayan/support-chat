"""Central human-handoff seam: context row, state, copy, events."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.outcome_copy import handoff_copy
from app.chat.state_machine import apply_event
from app.models.handoff_context import HandoffContext
from app.models.handoff_outcome import HANDOFF_OUTCOMES
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.handoff_repo import HandoffRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.site_repo import SiteRepository
from app.services import handoff_summary
from app.services.bot_trace import record_trace, register_trace_task

log = structlog.get_logger("handoff")

EscalationReason = Literal[
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
]

ProviderStatus = Literal["ok", "timeout", "error", "rate_limited"]
HandoffOutcomeValue = Literal[
    "resolved", "callback_completed", "no_response", "abandoned", "duplicate"
]

NOTE_MAX = 280


@dataclass(frozen=True)
class HandoffTrigger:
    conversation_id: UUID
    reason: EscalationReason
    original_question: str
    clarification_answer: str | None = None
    candidate_unit_ids: list[UUID] = field(default_factory=list)
    rejection_reasons: list[dict] = field(default_factory=list)
    stage_timings: dict[str, int] = field(default_factory=dict)
    provider_status: ProviderStatus = "ok"
    snapshot_id: UUID | None = None


class HandoffError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class HandoffService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._handoffs = HandoffRepository(session)
        self._conversations = ConversationRepository(session)
        self._messages = MessageRepository(session)
        self._sites = SiteRepository(session)

    async def open_handoff(self, trigger: HandoffTrigger) -> HandoffContext:
        conversation = await self._conversations.lock_by_id(trigger.conversation_id)
        if conversation is None:
            raise HandoffError("not_found")
        site = await self._sites.get_by_id(conversation.site_id)
        if site is None:
            raise HandoffError("not_found")

        existing = await self._handoffs.get_latest_for_conversation(conversation.id)
        if existing is not None:
            outcome = await self._handoffs.get_outcome(existing.id)
            if outcome is None:
                return existing

        route: Literal["live_queue", "callback"]
        promised: datetime | None = None
        window = int(getattr(site, "callback_window_hours", 24) or 24)
        if site.human_enabled:
            route = "live_queue"
            conversation.attention_needed = True
        else:
            route = "callback"
            conversation.attention_needed = True
            promised = datetime.now(UTC) + timedelta(hours=window)

        conversation.escalation_reason = trigger.reason
        conversation.active_generation_id = None
        if conversation.state == "bot":
            conversation.state = apply_event(conversation.state, "escalate")
        elif conversation.state == "prechat":
            conversation.state = apply_event(conversation.state, "capture")
        elif conversation.state not in {"queued", "human", "closed"}:
            conversation.state = apply_event(conversation.state, "escalate")

        row = await self._handoffs.create(
            conversation_id=conversation.id,
            site_id=site.id,
            escalation_reason=trigger.reason,
            original_question=(trigger.original_question or "").strip() or "(empty)",
            clarification_answer=trigger.clarification_answer,
            candidate_unit_ids=list(trigger.candidate_unit_ids),
            rejection_reasons=list(trigger.rejection_reasons),
            provider_stage_timings=dict(trigger.stage_timings or {}),
            provider_status=trigger.provider_status,
            promised_response_by=promised,
            route=route,
            snapshot_id=trigger.snapshot_id,
        )

        body = handoff_copy(trigger.reason, human_enabled=site.human_enabled, window_hours=window)
        await self._messages.create(
            conversation.id,
            "system",
            body,
            system_reason=trigger.reason,
        )
        conversation.last_message_at = datetime.now(UTC)
        await self._session.flush()

        log.info(
            "handoff_created",
            conversation_id=str(conversation.id),
            site_id=str(site.id),
            reason=trigger.reason,
            route=route,
            snapshot_id=str(trigger.snapshot_id) if trigger.snapshot_id else None,
            stage_timings=dict(trigger.stage_timings or {}),
            provider_status=trigger.provider_status,
        )
        record_trace(
            "handoff",
            handoff_id=row.id,
            reason=trigger.reason,
            route=route,
            state=conversation.state,
            promised_response_by=promised,
        )
        return row

    def schedule_summary(self, row: HandoffContext) -> None:
        record_trace("handoff_summary", status="pending", handoff_id=row.id, persisted=False)
        task = asyncio.create_task(
            handoff_summary.generate_in_background(
                row.id,
                row.conversation_id,
                row.original_question,
                row.escalation_reason,
            )
        )
        register_trace_task(task)
        task.add_done_callback(lambda _: None)

    async def close_handoff(
        self,
        handoff_id: UUID,
        outcome: HandoffOutcomeValue,
        resolver_id: UUID,
        note: str | None,
    ) -> None:
        if outcome not in HANDOFF_OUTCOMES:
            raise HandoffError("invalid")
        cleaned = None
        if note is not None:
            cleaned = note.strip()
            if len(cleaned) > NOTE_MAX:
                raise HandoffError("invalid")
            if not cleaned:
                cleaned = None
        row = await self._handoffs.get_by_id(handoff_id)
        if row is None:
            raise HandoffError("not_found")
        existing = await self._handoffs.get_outcome(handoff_id)
        if existing is not None:
            raise HandoffError("already_resolved")
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        try:
            await self._handoffs.create_outcome(
                handoff_id=handoff_id,
                resolved_by=resolver_id,
                outcome=outcome,
                note=cleaned,
            )
        except IntegrityError as exc:
            raise HandoffError("already_resolved") from exc
        elapsed = round((datetime.now(UTC) - created).total_seconds() * 1000)
        log.info(
            "handoff_resolved",
            handoff_id=str(handoff_id),
            outcome=outcome,
            resolver_id=str(resolver_id),
            time_to_resolve_ms=elapsed,
        )

    async def get_active_for(self, conversation_id: UUID) -> HandoffContext | None:
        return await self._handoffs.get_latest_for_conversation(conversation_id)

    async def get_detail(self, conversation_id: UUID) -> dict | None:
        row = await self.get_active_for(conversation_id)
        if row is None:
            return None
        outcome = await self._handoffs.get_outcome(row.id)
        return _serialize_handoff(row, outcome)

    async def get_detail_by_id(self, handoff_id: UUID) -> dict | None:
        row = await self._handoffs.get_by_id(handoff_id)
        if row is None:
            return None
        outcome = await self._handoffs.get_outcome(row.id)
        return _serialize_handoff(row, outcome)

    async def regenerate_summary(self, handoff_id: UUID) -> HandoffContext:
        row = await self._handoffs.get_by_id(handoff_id)
        if row is None:
            raise HandoffError("not_found")
        await handoff_summary.generate(
            self._session,
            handoff_id=row.id,
            conversation_id=row.conversation_id,
            original_question=row.original_question,
            escalation_reason=row.escalation_reason,
        )
        refreshed = await self._handoffs.get_by_id(handoff_id)
        if refreshed is None:
            raise HandoffError("not_found")
        return refreshed

    async def candidate_labels(self, unit_ids: list[UUID]) -> dict[UUID, dict]:
        if not unit_ids:
            return {}
        from sqlalchemy import select

        from app.models.kb_chunk import KbChunk

        result = await self._session.execute(select(KbChunk).where(KbChunk.id.in_(unit_ids)))
        out: dict[UUID, dict] = {}
        for chunk in result.scalars().all():
            out[chunk.id] = {
                "canonical_question": chunk.canonical_question,
                "heading": chunk.heading,
            }
        return out


def _serialize_handoff(row: HandoffContext, outcome) -> dict:
    return {
        "id": str(row.id),
        "conversation_id": str(row.conversation_id),
        "site_id": str(row.site_id),
        "created_at": row.created_at,
        "escalation_reason": row.escalation_reason,
        "original_question": row.original_question,
        "clarification_answer": row.clarification_answer,
        "machine_summary": row.machine_summary,
        "machine_summary_model": row.machine_summary_model,
        "candidate_unit_ids": [str(item) for item in (row.candidate_unit_ids or [])],
        "rejection_reasons": list(row.rejection_reasons or []),
        "provider_stage_timings": dict(row.provider_stage_timings or {}),
        "provider_status": row.provider_status,
        "promised_response_by": row.promised_response_by,
        "route": row.route,
        "snapshot_id": str(row.snapshot_id) if row.snapshot_id else None,
        "outcome": (
            None
            if outcome is None
            else {
                "outcome": outcome.outcome,
                "note": outcome.note,
                "resolved_at": outcome.resolved_at,
                "resolved_by": str(outcome.resolved_by) if outcome.resolved_by else None,
            }
        ),
    }
