import asyncio

import structlog

from app.redis import get_redis

log = structlog.get_logger("worker_health")
HEARTBEAT_KEY = "worker:healthy"
HEARTBEAT_INTERVAL = 5.0
HEARTBEAT_TTL = 20
_task: asyncio.Task | None = None


async def worker_heartbeat_loop() -> None:
    while True:
        try:
            await get_redis().set(HEARTBEAT_KEY, "1", ex=HEARTBEAT_TTL)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.info("worker_heartbeat_failed", error_class=type(exc).__name__)
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def start_worker_heartbeat() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(worker_heartbeat_loop())


async def stop_worker_heartbeat() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
