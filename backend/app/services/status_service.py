"""Staff desk snapshot: infrastructure, inbox load, knowledge, recent failures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.connection_manager import connection_manager
from app.redis import get_redis
from app.repositories.app_log_repo import AppLogRepository
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.kb_source_repo import KbSourceRepository
from app.repositories.knowledge_gap_repo import KnowledgeGapRepository
from app.services.status_history import build_status_history
from app.workers.health import HEARTBEAT_KEY

ServiceState = Literal["ok", "down", "silent"]
OverallState = Literal["ok", "attention", "degraded"]
KnowledgeTone = Literal["none", "ready", "queued", "running", "failed"]

_SOURCE_RANK = {"failed": 0, "running": 1, "queued": 2, "ready": 3}
RECENT_ERROR_LIMIT = 5


def _utc_day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _worst_knowledge(statuses: list[str]) -> KnowledgeTone:
    ranked = [status for status in statuses if status in _SOURCE_RANK]
    if not ranked:
        return "none"
    return min(ranked, key=_SOURCE_RANK.__getitem__)  # type: ignore[return-value]


def _headline(
    *,
    postgres: ServiceState,
    redis: ServiceState,
    worker: ServiceState,
    knowledge_failed: int,
) -> tuple[OverallState, str]:
    if postgres != "ok":
        return "degraded", "Postgres is down"
    if redis != "ok":
        return "degraded", "Redis is down"
    if worker != "ok":
        return "attention", "Background work is silent"
    if knowledge_failed:
        return "attention", "Knowledge ingest failed"
    return "ok", "All systems answering"


async def _probe_redis() -> tuple[ServiceState, ServiceState]:
    try:
        await get_redis().ping()
    except Exception:
        return "down", "silent"
    try:
        beat = await get_redis().get(HEARTBEAT_KEY)
    except Exception:
        return "ok", "silent"
    if beat:
        return "ok", "ok"
    return "ok", "silent"


async def build_status_snapshot(session: AsyncSession) -> dict[str, Any]:
    now = datetime.now(UTC)
    redis_state, worker_state = await _probe_redis()
    conversations = ConversationRepository(session)
    inbox = await conversations.count_inbox_by_state()
    closed_today = await conversations.count_closed_since(_utc_day_start(now))
    sites = await conversations.list_inbox_sites()
    sources = await KbSourceRepository(session).list_enabled()
    knowledge_counts = {"ready": 0, "running": 0, "failed": 0, "queued": 0}
    sources_by_site: dict[UUID, list[str]] = {}
    for source in sources:
        if source.status in knowledge_counts:
            knowledge_counts[source.status] += 1
        sources_by_site.setdefault(source.site_id, []).append(source.status)
    errors_since = now - timedelta(hours=24)
    logs = AppLogRepository(session)
    recent_errors = await logs.list_recent(
        since=errors_since, level="error", limit=RECENT_ERROR_LIMIT
    )
    overall, headline = _headline(
        postgres="ok",
        redis=redis_state,
        worker=worker_state,
        knowledge_failed=knowledge_counts["failed"],
    )
    services = {
        "api": "ok",
        "postgres": "ok",
        "redis": redis_state,
        "worker": worker_state,
    }
    history = await build_status_history(session, now, services)
    return {
        "checked_at": now,
        "overall": overall,
        "headline": headline,
        "services": services,
        "live": {
            "visitors": connection_manager.live_visitor_count(),
            "specialists": connection_manager.live_specialist_count(),
        },
        "inbox": {
            "waiting": inbox["queued"],
            "bot": inbox["bot"],
            "live": inbox["human"],
            "closed_today": closed_today,
        },
        "knowledge": knowledge_counts,
        "gaps_open": await KnowledgeGapRepository(session).count_with_status("open"),
        "errors_24h": await logs.count_level_since(level="error", since=errors_since),
        "recent_errors": [
            {
                "id": row.id,
                "created_at": row.created_at,
                "event": row.event,
                "message": row.message,
                "source": row.source,
            }
            for row in recent_errors
        ],
        "sites": [
            {
                "id": site.id,
                "key": site.key,
                "name": site.name,
                "enabled": site.enabled,
                "bot_enabled": site.bot_enabled,
                "human_enabled": site.human_enabled,
                "widget_installed": site.widget_installed,
                "waiting": waiting,
                "knowledge": _worst_knowledge(sources_by_site.get(site.id, [])),
            }
            for site, waiting in sites
        ],
        "uptime": history["uptime"],
        "monitors": history["monitors"],
        "incidents": history["incidents"],
    }
