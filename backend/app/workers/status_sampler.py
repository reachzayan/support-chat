import asyncio
import time

import httpx
import structlog
from sqlalchemy import text

from app.db import get_engine, session_maker
from app.redis import get_redis
from app.repositories.status_sample_repo import StatusSampleRepository
from app.settings import get_settings
from app.workers.health import HEARTBEAT_KEY

log = structlog.get_logger("status_sampler")
SAMPLE_INTERVAL = 30.0
_task: asyncio.Task | None = None


async def _timed_postgres() -> tuple[bool, int | None]:
    started = time.perf_counter()
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True, int((time.perf_counter() - started) * 1000)
    except Exception:
        return False, None


async def _timed_redis() -> tuple[bool, int | None]:
    started = time.perf_counter()
    try:
        await get_redis().ping()
        return True, int((time.perf_counter() - started) * 1000)
    except Exception:
        return False, None


async def _worker_beat() -> tuple[bool, int | None]:
    try:
        beat = await get_redis().get(HEARTBEAT_KEY)
    except Exception:
        return False, None
    return bool(beat), None


async def _timed_api() -> tuple[bool, int | None]:
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(get_settings().status_api_probe_url)
        return response.status_code < 500, int((time.perf_counter() - started) * 1000)
    except Exception:
        return False, None


async def collect_probes() -> list[tuple[str, bool, int | None]]:
    postgres_ok, postgres_ms = await _timed_postgres()
    redis_ok, redis_ms = await _timed_redis()
    worker_ok, worker_ms = await _worker_beat()
    api_ok, api_ms = await _timed_api()
    return [
        ("api", api_ok, api_ms),
        ("postgres", postgres_ok, postgres_ms),
        ("redis", redis_ok, redis_ms),
        ("worker", worker_ok, worker_ms),
    ]


async def record_status_samples() -> None:
    rows = await collect_probes()
    async with session_maker()() as session:
        await StatusSampleRepository(session).add_many(rows)
        await session.commit()


async def status_sampler_loop() -> None:
    while True:
        try:
            await record_status_samples()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.info("status_sample_failed")
        await asyncio.sleep(SAMPLE_INTERVAL)


async def start_status_sampler() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(status_sampler_loop())


async def stop_status_sampler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
