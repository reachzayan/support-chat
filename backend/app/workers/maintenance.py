import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from scripts.purge_expired_chats import purge_expired
from scripts.purge_expired_logs import purge_expired_logs
from scripts.purge_expired_refresh_tokens import purge_expired_refresh_tokens

log = structlog.get_logger("maintenance")
SLEEP_SECONDS = 3600
_last_chat_purge_at: datetime | None = None


async def run_maintenance_once() -> None:
    global _last_chat_purge_at
    now = datetime.now(UTC)
    if _last_chat_purge_at is None or now - _last_chat_purge_at >= timedelta(days=1):
        await purge_expired(now=now)
        _last_chat_purge_at = now
    await purge_expired_logs(now=now)
    await purge_expired_refresh_tokens(now=now)


async def maintenance_loop() -> None:
    while True:
        try:
            await run_maintenance_once()
        except Exception:
            log.info("maintenance_failed")
        await asyncio.sleep(SLEEP_SECONDS)


_maintenance_task: asyncio.Task | None = None


async def start_maintenance_worker() -> None:
    global _maintenance_task
    if _maintenance_task is not None and not _maintenance_task.done():
        return
    _maintenance_task = asyncio.create_task(maintenance_loop())


async def stop_maintenance_worker() -> None:
    global _maintenance_task
    if _maintenance_task is None:
        return
    _maintenance_task.cancel()
    try:
        await _maintenance_task
    except asyncio.CancelledError:
        pass
    _maintenance_task = None
