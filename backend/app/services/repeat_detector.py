"""Deterministic repeat / frustration detector for forced handoff."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.intent import normalize_text
from app.models.message import Message

_MISS_REASONS = (
    "insufficient",
    "tech_fail",
    "retrieval_miss",
    "sufficiency_fail",
    "provider_timeout",
)
_WINDOW = timedelta(minutes=15)


async def should_force_repeated_miss(
    session: AsyncSession,
    conversation_id: UUID,
    normalized_current_question: str,
    *,
    now: datetime | None = None,
) -> bool:
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    since = moment - _WINDOW

    miss_count = await session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role.in_(("bot", "system")),
            Message.system_reason.in_(_MISS_REASONS),
            Message.created_at > since,
        )
    )
    if int(miss_count or 0) >= 2:
        return True

    needle = normalize_text(normalized_current_question)
    if not needle:
        return False
    visitor_rows = await session.execute(
        select(Message.body).where(
            Message.conversation_id == conversation_id,
            Message.role == "visitor",
        )
    )
    same = sum(1 for (body,) in visitor_rows.all() if normalize_text(body or "") == needle)
    return same >= 3
