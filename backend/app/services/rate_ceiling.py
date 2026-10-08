"""Per-conversation Anthropic call ceiling (denial-of-wallet control)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
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


class TurnBudget:
    """Charges every Anthropic call of one bot turn to its conversation's ceiling.

    Once the ceiling is hit or Redis is unavailable, the turn is `tripped` and no
    further call is made, so the caller can answer with one safe decision.
    """

    def __init__(self, conversation_id: UUID, ceiling: RateCeiling | None = None) -> None:
        self._conversation_id = conversation_id
        self._ceiling = ceiling or RateCeiling()
        self.tripped: type[Exception] | None = None

    async def charge(self) -> None:
        if self.tripped is not None:
            raise self.tripped()
        try:
            await self._ceiling.hit_or_raise(self._conversation_id)
        except (RateLimitExceeded, RateLimitUnavailable) as exc:
            self.tripped = type(exc)
            raise


_current_budget: ContextVar[TurnBudget | None] = ContextVar("anthropic_turn_budget", default=None)


@contextmanager
def bind_turn_budget(budget: TurnBudget) -> Iterator[TurnBudget]:
    token = _current_budget.set(budget)
    try:
        yield budget
    finally:
        _current_budget.reset(token)


async def charge_anthropic_call() -> None:
    """Count one Claude call against the bound turn budget (no-op outside a bot turn)."""
    budget = _current_budget.get()
    if budget is not None:
        await budget.charge()
