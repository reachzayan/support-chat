from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.handoff_context import HandoffContext
from app.models.handoff_outcome import HandoffOutcome


class HandoffRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        conversation_id: UUID,
        site_id: UUID,
        escalation_reason: str,
        original_question: str,
        clarification_answer: str | None,
        candidate_unit_ids: list[UUID],
        rejection_reasons: list,
        provider_stage_timings: dict,
        provider_status: str,
        promised_response_by: datetime | None,
        route: str,
        snapshot_id: UUID | None,
        machine_summary: str = "",
        machine_summary_model: str = "",
    ) -> HandoffContext:
        row = HandoffContext(
            conversation_id=conversation_id,
            site_id=site_id,
            escalation_reason=escalation_reason,
            original_question=original_question,
            clarification_answer=clarification_answer,
            machine_summary=machine_summary,
            machine_summary_model=machine_summary_model,
            candidate_unit_ids=list(candidate_unit_ids),
            rejection_reasons=list(rejection_reasons),
            provider_stage_timings=dict(provider_stage_timings),
            provider_status=provider_status,
            promised_response_by=promised_response_by,
            route=route,
            snapshot_id=snapshot_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_id(self, handoff_id: UUID) -> HandoffContext | None:
        result = await self._session.execute(
            select(HandoffContext).where(HandoffContext.id == handoff_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_for_conversation(self, conversation_id: UUID) -> HandoffContext | None:
        result = await self._session.execute(
            select(HandoffContext)
            .where(HandoffContext.conversation_id == conversation_id)
            .order_by(HandoffContext.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_outcome(self, handoff_id: UUID) -> HandoffOutcome | None:
        result = await self._session.execute(
            select(HandoffOutcome).where(HandoffOutcome.handoff_id == handoff_id)
        )
        return result.scalar_one_or_none()

    async def create_outcome(
        self,
        *,
        handoff_id: UUID,
        resolved_by: UUID | None,
        outcome: str,
        note: str | None,
    ) -> HandoffOutcome:
        row = HandoffOutcome(
            handoff_id=handoff_id,
            resolved_by=resolved_by,
            outcome=outcome,
            note=note,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def update_summary(
        self, handoff_id: UUID, summary: str, model: str
    ) -> HandoffContext | None:
        row = await self.get_by_id(handoff_id)
        if row is None:
            return None
        row.machine_summary = summary
        row.machine_summary_model = model
        row.summary_status = "completed"
        row.summary_lease_expires_at = None
        row.summary_error = None
        await self._session.flush()
        return row

    async def claim_next_summary(self, *, lease: timedelta) -> HandoffContext | None:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(HandoffContext)
            .where(
                or_(
                    and_(
                        HandoffContext.summary_status == "queued",
                        HandoffContext.summary_next_run_at <= now,
                    ),
                    and_(
                        HandoffContext.summary_status == "running",
                        HandoffContext.summary_lease_expires_at <= now,
                    ),
                )
            )
            .order_by(HandoffContext.summary_next_run_at, HandoffContext.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        row = result.scalar_one_or_none()
        if row is None:
            await self._session.commit()
            return None
        row.summary_status = "running"
        row.summary_attempts += 1
        row.summary_lease_expires_at = now + lease
        row.summary_error = None
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def retry_or_fail_summary(
        self,
        handoff_id: UUID,
        *,
        error: str,
        max_attempts: int,
        retry_delay: timedelta,
    ) -> None:
        row = await self.get_by_id(handoff_id)
        if row is None:
            return
        row.summary_error = error[:128]
        row.summary_lease_expires_at = None
        if row.summary_attempts >= max_attempts:
            row.summary_status = "failed"
        else:
            row.summary_status = "queued"
            row.summary_next_run_at = datetime.now(UTC) + retry_delay
        await self._session.flush()
