from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Literal
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.faq_fastpath import normalize_fast_query, try_fast_answer
from app.services.kb_tokens import is_overview_query
from app.settings import get_settings

log = structlog.get_logger("route_decision")

RoutePath = Literal["escalate", "sensitive", "fast", "full_context", "hybrid"]


@dataclass(frozen=True)
class RouteDecision:
    path: RoutePath
    reason: str
    snapshot_id: UUID | None
    snapshot_ids: tuple[UUID, ...] = ()
    token_estimate: int = 0
    elapsed_ms: int = 0
    fast_path_ms: int | None = None


async def live_snapshots_for_site(session: AsyncSession, site_id: UUID) -> list[KbSnapshot]:
    result = await session.execute(
        select(KbSnapshot)
        .join(KbSource, KbSource.id == KbSnapshot.source_id)
        .where(
            KbSnapshot.site_id == site_id,
            KbSnapshot.state == "live",
            KbSource.enabled.is_(True),
        )
        .order_by(KbSnapshot.promoted_at.desc().nullslast(), KbSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


async def decide(
    session: AsyncSession,
    *,
    site_id: UUID,
    visitor_text: str,
    intent: str | None,
    sensitive: bool,
    escalate: bool,
) -> RouteDecision:
    started = time.perf_counter()
    if sensitive:
        return _finish(
            RouteDecision(path="sensitive", reason="sensitive_intent", snapshot_id=None),
            started,
        )
    if escalate or intent == "escalate":
        return _finish(
            RouteDecision(path="escalate", reason="escalate_intent", snapshot_id=None),
            started,
        )

    snapshots = await live_snapshots_for_site(session, site_id)
    snapshot_ids = tuple(item.id for item in snapshots)
    token_estimate = sum(int(item.token_estimate or 0) for item in snapshots)
    primary_id = snapshot_ids[0] if snapshot_ids else None

    settings = get_settings()
    candidate: RoutePath = (
        "full_context" if token_estimate < settings.full_context_max_tokens else "hybrid"
    )
    if not snapshot_ids:
        return _finish(
            RouteDecision(
                path="hybrid",
                reason="no_live_snapshot",
                snapshot_id=None,
                snapshot_ids=(),
                token_estimate=0,
            ),
            started,
        )

    if is_overview_query(visitor_text):
        return _finish(
            RouteDecision(
                path=candidate,
                reason="overview_query",
                snapshot_id=primary_id,
                snapshot_ids=snapshot_ids,
                token_estimate=token_estimate,
            ),
            started,
        )

    normalized = normalize_fast_query(visitor_text)
    fast_path_ms: int | None = None
    if normalized is not None:
        fast_started = time.perf_counter()
        fast = await try_fast_answer(session, site_id, list(snapshot_ids), normalized)
        fast_path_ms = round((time.perf_counter() - fast_started) * 1000)
        if fast is not None:
            return _finish(
                RouteDecision(
                    path="fast",
                    reason="faq_fastpath",
                    snapshot_id=fast.snapshot_id,
                    snapshot_ids=snapshot_ids,
                    token_estimate=token_estimate,
                    fast_path_ms=fast_path_ms,
                ),
                started,
            )

    return _finish(
        RouteDecision(
            path=candidate,
            reason="token_estimate" if candidate == "full_context" else "over_threshold",
            snapshot_id=primary_id,
            snapshot_ids=snapshot_ids,
            token_estimate=token_estimate,
            fast_path_ms=fast_path_ms,
        ),
        started,
    )


def _finish(decision: RouteDecision, started: float) -> RouteDecision:
    elapsed = (time.perf_counter() - started) * 1000
    finished = replace(decision, elapsed_ms=round(elapsed))
    log.info(
        "route_decision",
        path=finished.path,
        reason=finished.reason,
        snapshot_id=str(finished.snapshot_id) if finished.snapshot_id else None,
        token_estimate=finished.token_estimate,
        elapsed_ms=round(elapsed, 2),
    )
    return finished


async def site_token_estimate(session: AsyncSession, site_id: UUID) -> int:
    result = await session.execute(
        select(func.coalesce(func.sum(KbSnapshot.token_estimate), 0))
        .join(KbSource, KbSource.id == KbSnapshot.source_id)
        .where(
            KbSnapshot.site_id == site_id,
            KbSnapshot.state == "live",
            KbSource.enabled.is_(True),
        )
    )
    return int(result.scalar_one())
