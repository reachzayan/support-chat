import asyncio
from uuid import UUID

import redis.asyncio as redis
import structlog
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy import select

from app.db import session_maker
from app.models.kb_snapshot import KbSnapshot
from app.repositories.kb_page_job_repo import KbPageJobRepository
from app.repositories.kb_source_repo import KbSourceRepository
from app.services.kb_embedder import default_embedder
from app.services.kb_ingest import INGEST_KEY, ingest_source
from app.services.kb_llm_extract import default_llm_client
from app.settings import get_settings

log = structlog.get_logger("kb_ingest")
RETRY_SLEEP = 1.0

_worker_task: asyncio.Task | None = None
_queue_client: redis.Redis | None = None


def _queue_redis() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
    )


async def _close_queue_client() -> None:
    global _queue_client
    if _queue_client is None:
        return
    try:
        await _queue_client.aclose()
    except Exception:
        pass
    _queue_client = None


async def start_ingest_worker() -> None:
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(run_worker())


async def stop_ingest_worker() -> None:
    global _worker_task
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
    await _close_queue_client()


async def _wait_wakeup(lock: asyncio.Lock) -> UUID | None:
    global _queue_client
    async with lock:
        try:
            if _queue_client is None:
                _queue_client = _queue_redis()
            item = await _queue_client.blpop(INGEST_KEY, timeout=5)
        except asyncio.CancelledError:
            raise
        except (TimeoutError, RedisTimeoutError):
            return None
        except Exception as exc:
            log.info("ingest_poll_failed", error=type(exc).__name__)
            await _close_queue_client()
            await asyncio.sleep(RETRY_SLEEP)
            return None
        if item is None:
            return None
        _key, raw = item
        try:
            return UUID(str(raw))
        except ValueError:
            return None


async def _drain_queued(hinted: UUID | None, embedder) -> None:
    while True:
        async with session_maker()() as session:
            await KbPageJobRepository(session).reap_stuck()
            await session.commit()
            claimed = await KbSourceRepository(session).claim_next(hinted)
            hinted = None
            if claimed is None:
                return
            source_id = claimed.id
            try:
                async with asyncio.timeout(get_settings().kb_ingest_source_timeout_seconds):
                    await ingest_source(
                        session,
                        source_id,
                        embedder=embedder,
                        llm_client=default_llm_client(),
                    )
            except Exception as exc:
                error_code = "timeout" if isinstance(exc, TimeoutError) else "ingest"
                log.info(
                    "ingest_job_failed",
                    source_id=str(source_id),
                    error=type(exc).__name__,
                )
                await session.rollback()
                claimed = await KbSourceRepository(session).lock_by_id(source_id)
                if claimed is not None:
                    claimed.status = "failed"
                    claimed.stage = "failed"
                    claimed.error_code = error_code
                    claimed.last_error_code = error_code
                    building = await session.scalar(
                        select(KbSnapshot)
                        .where(
                            KbSnapshot.source_id == source_id,
                            KbSnapshot.state.in_(("building", "validated")),
                        )
                        .order_by(KbSnapshot.created_at.desc())
                    )
                    if building is not None:
                        building.state = "failed"
                        building.error_code = error_code
                    await session.commit()
                continue


async def _source_loop(embedder, lock: asyncio.Lock) -> None:
    while True:
        hinted = await _wait_wakeup(lock)
        await _drain_queued(hinted, embedder)


async def run_worker() -> None:
    embedder = default_embedder()
    workers = max(1, get_settings().kb_ingest_source_concurrency)
    blpop_lock = asyncio.Lock()
    try:
        async with asyncio.TaskGroup() as tg:
            for _ in range(workers):
                tg.create_task(_source_loop(embedder, blpop_lock))
    finally:
        await _close_queue_client()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
