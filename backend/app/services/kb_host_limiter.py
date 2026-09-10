from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse


class HostLimiter:
    def __init__(self, delay_ms: int) -> None:
        self._delay = max(delay_ms, 0) / 1000.0
        self._locks: dict[str, asyncio.Lock] = {}
        self._last: dict[str, float] = {}

    async def wait(self, host: str) -> None:
        key = (host or "").casefold()
        if self._delay <= 0 or not key:
            return
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            last = self._last.get(key)
            if last is not None:
                remaining = self._delay - (time.monotonic() - last)
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last[key] = time.monotonic()

    async def wait_url(self, url: str) -> None:
        await self.wait(urlparse(url).hostname or "")
