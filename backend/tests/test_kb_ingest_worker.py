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


async def test_drain_continues_after_one_source_fails(migrated_db, monkeypatch) -> None:
    from sqlalchemy.exc import DBAPIError

    from app.db import session_maker
    from app.models.kb_source import KbSource
    from app.services.kb_embedder import FakeEmbedder, configured_embedder_id
    from app.workers.kb_ingest_worker import _drain_queued
    from tests.bot_fixtures import insert_site

    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        site.allowed_origins = ["https://sample-site.example.com"]
        failed = KbSource(
            site_id=site.id,
            start_url="https://sample-site.example.com/a",
            mode="list",
            seed_urls=["https://sample-site.example.com/a"],
            status="queued",
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        ready = KbSource(
            site_id=site.id,
            start_url="https://sample-site.example.com/faq",
            mode="list",
            seed_urls=["https://sample-site.example.com/faq"],
            status="queued",
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add_all([failed, ready])
        await session.commit()
        failed_id, ready_id = failed.id, ready.id

    async def ingest(session, source_id, **_kwargs):
        if source_id == failed_id:
            raise DBAPIError("SELECT 1", {}, Exception("ingest failed"))
        source = await session.get(KbSource, source_id)
        assert source is not None
        source.status = "ready"
        source.stage = "ready"
        await session.commit()

    monkeypatch.setattr("app.workers.kb_ingest_worker.ingest_source", ingest)
    monkeypatch.setattr("app.workers.kb_ingest_worker.default_llm_client", lambda: None)
    await _drain_queued(None, FakeEmbedder())

    async with session_maker()() as session:
        failed_row = await session.get(KbSource, failed_id)
        ready_row = await session.get(KbSource, ready_id)
        assert failed_row is not None
        assert ready_row is not None
        assert failed_row.status == "failed"
        assert ready_row.status == "ready"
