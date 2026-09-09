"""Per-conversation Anthropic call ceiling (denial-of-wallet control)."""

from __future__ import annotations

from uuid import UUID

import structlog

from app.redis import get_redis
from app.services.rate_limit import INCR_EXPIRE, RateLimitExceeded, RateLimitUnavailable
from app.settings import Settings, get_settings

log = structlog.get_logger("rate_ceiling")

WINDOW_SECONDS = 60


class RateCeiling:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _key(self, conversation_id: UUID) -> str:
        return f"ratekey:{conversation_id}:anthropic"

    async def allow(self, conversation_id: UUID) -> bool:
        """Return True if another Anthropic call is within budget; False if over ceiling."""
        budget = self._settings.anthropic_calls_per_minute
        key = self._key(conversation_id)
        try:
            count = int(await get_redis().eval(INCR_EXPIRE, 1, key, str(WINDOW_SECONDS)))
        except Exception as exc:
            raise RateLimitUnavailable() from exc
        if count > budget:
            log.info(
                "rate_ceiling_hit",
                conversation_id=str(conversation_id),
                count=count,
                budget=budget,
            )
            return False
        return True

    async def hit_or_raise(self, conversation_id: UUID) -> None:
        if not await self.allow(conversation_id):
            raise RateLimitExceeded()
