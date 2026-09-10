import asyncio

from app.workers.kb_ingest_worker import run_worker


class _IdleThenHangRedis:
    def __init__(self) -> None:
        self.blpop_calls = 0

    async def blpop(self, _key: str, timeout: int = 5):
        self.blpop_calls += 1
        if self.blpop_calls == 1:
            raise TimeoutError("Timeout reading from 127.0.0.1:56379")
        await asyncio.Event().wait()
        return None

    async def aclose(self) -> None:
        return None


async def test_ingest_worker_keeps_polling_after_idle_blpop_timeout(monkeypatch) -> None:
    redis = _IdleThenHangRedis()
    monkeypatch.setattr("app.workers.kb_ingest_worker._queue_redis", lambda: redis)

    async def _no_jobs(_hinted, _embedder) -> None:
        return None

    monkeypatch.setattr("app.workers.kb_ingest_worker._drain_queued", _no_jobs)
    task = asyncio.create_task(run_worker())
    try:
        for _ in range(50):
            if redis.blpop_calls >= 2:
                break
            await asyncio.sleep(0.01)
        assert redis.blpop_calls >= 2
        assert task.done() is False
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
