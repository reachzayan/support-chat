import asyncio

import structlog

from app.chat.connection_manager import connection_manager
from app.db import session_maker
from app.services.conversation_service import ConversationService

log = structlog.get_logger("idle_close")
SWEEP_SECONDS = 15

_worker_task: asyncio.Task | None = None


async def start_idle_closer() -> None:
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_run())


async def stop_idle_closer() -> None:
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None


async def _run() -> None:
    while True:
        await asyncio.sleep(SWEEP_SECONDS)
        try:
            async with session_maker()() as session:
                closed = await ConversationService(session).close_expired()
            for result in closed:
                await connection_manager.after_commit(result.conversation, result.site_key, None)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.info("idle_close_failed", role="system", length=0)
