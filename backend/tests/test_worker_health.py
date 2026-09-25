import asyncio

from app.workers import health


async def test_worker_heartbeat_refreshes_expiring_redis_key(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    class _Redis:
        async def set(self, key: str, value: str, *, ex: int) -> None:
            calls.append((key, value, ex))

    monkeypatch.setattr(health, "get_redis", lambda: _Redis())
    monkeypatch.setattr(health, "HEARTBEAT_INTERVAL", 0.01)
    task = asyncio.create_task(health.worker_heartbeat_loop())
    try:
        for _ in range(20):
            if len(calls) >= 2:
                break
            await asyncio.sleep(0.01)
        assert len(calls) >= 2
        assert all(call == ("worker:healthy", "1", health.HEARTBEAT_TTL) for call in calls)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
