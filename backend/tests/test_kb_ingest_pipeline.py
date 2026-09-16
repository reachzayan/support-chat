import asyncio
from uuid import uuid4

from sqlalchemy import func, select

from app.db import session_maker
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_source import KbSource
from app.repositories.kb_source_repo import KbSourceRepository
from app.services.kb_embedder import FakeEmbedder, configured_embedder_id
from app.services.kb_ingest import canonical_url, ingest_source
from tests.bot_fixtures import insert_site

FAQ_URL = "https://sample-site.example.com/faq"
DOT_URL = "https://sample-site.example.com/dot"
HOME_URL = "https://sample-site.example.com/"
TIMING_HTML = (
    "<html><body><main><h1>Turnaround</h1>"
    "<p>Most negative results are reported within 24-48 hours.</p></main></body></html>"
)
DOT_HTML = (
    "<html><body><main><h1>DOT</h1>"
    "<p>DOT-regulated testing follows federal rules for prohibited substances.</p>"
    "</main></body></html>"
)
PAGES = {FAQ_URL: TIMING_HTML, DOT_URL: DOT_HTML, HOME_URL: TIMING_HTML}


def fake_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
    return PAGES[url]


class CountingEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        self.document_calls = 0

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return await super().embed_documents(texts)


async def _queued_source(session, seed_urls: list[str]) -> KbSource:
    site = await insert_site(session, f"easy-{uuid4().hex[:8]}", "SampleSite")
    site.allowed_origins = ["https://sample-site.example.com"]
    source = KbSource(
        site_id=site.id,
        start_url=seed_urls[0],
        mode="list",
        seed_urls=seed_urls,
        status="queued",
        embedder_id=configured_embedder_id(),
        enabled=True,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


def test_canonical_url_strips_fragment_and_fills_root_path() -> None:
    assert canonical_url("https://sample-site.example.com/#faq") == HOME_URL
    assert canonical_url("https://sample-site.example.com/") == HOME_URL
    assert canonical_url("https://sample-site.example.com/faq#timing") == FAQ_URL


async def test_claim_takes_queued_row_without_redis_wakeup(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        claimed = await KbSourceRepository(session).claim_next(None)
        assert claimed is not None
        assert claimed.id == source.id
        assert claimed.status == "running"


async def test_claim_ignores_ready_source_even_when_woken(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        source.status = "ready"
        source.page_count = 1
        await session.commit()
        claimed = await KbSourceRepository(session).claim_next(source.id)
        assert claimed is None


async def test_second_ingest_does_not_duplicate_pages_or_reembed(migrated_db) -> None:
    embedder = CountingEmbedder()
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL, DOT_URL])
        source_id = source.id
        await ingest_source(session, source_id, embedder=embedder, fetch=fake_fetch)
        first_calls = embedder.document_calls
        assert first_calls == 2
        source.status = "queued"
        await session.commit()
        await ingest_source(session, source_id, embedder=embedder, fetch=fake_fetch)

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "ready"
        assert source.page_count == 2
        page_count = await session.scalar(
            select(func.count()).select_from(KbPage).where(KbPage.source_id == source_id)
        )
        chunk_count = await session.scalar(
            select(func.count())
            .select_from(KbChunk)
            .join(KbPage, KbChunk.page_id == KbPage.id)
            .where(KbPage.source_id == source_id)
        )
        assert page_count == 2
        assert chunk_count == 2
        assert embedder.document_calls == first_calls


async def test_worker_drains_queued_source_when_redis_wakeup_is_missing(
    migrated_db, monkeypatch
) -> None:
    from app.workers import kb_ingest_worker

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

    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        source_id = source.id

    from app.services.kb_fetcher import FetchResult, _digest

    async def _fake_page(url: str, allowed_hosts: set[str], fetch=None, crawler=None):
        html = fake_fetch(url, allowed_hosts)
        return FetchResult(
            url=url,
            status=200,
            html=html,
            markdown="",
            content_sha256=_digest(html),
            renderer="injected",
        )

    redis = _IdleThenHangRedis()
    monkeypatch.setattr(kb_ingest_worker, "_queue_redis", lambda: redis)
    monkeypatch.setattr(kb_ingest_worker, "default_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr("app.services.kb_pipeline.fetch_page", _fake_page)
    monkeypatch.setattr("app.services.kb_crawl.fetch_html", fake_fetch)
    task = asyncio.create_task(kb_ingest_worker.run_worker())
    try:
        for _ in range(100):
            async with session_maker()() as session:
                row = await session.get(KbSource, source_id)
                assert row is not None
                if row.status == "ready" and row.page_count == 1:
                    break
            await asyncio.sleep(0.05)
        async with session_maker()() as session:
            row = await session.get(KbSource, source_id)
            assert row is not None
            assert row.status == "ready"
            assert row.page_count == 1
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def test_prefix_crawl_follows_links_beyond_the_first_frontier(migrated_db) -> None:
    pages = {
        HOME_URL: '<main><h1>Home</h1><p>Useful home page copy.</p><a href="/one">One</a></main>',
        "https://sample-site.example.com/one": (
            '<main><h1>One</h1><p>Useful first page copy.</p><a href="/two">Two</a></main>'
        ),
        "https://sample-site.example.com/two": (
            "<main><h1>Two</h1><p>Useful second page copy.</p></main>"
        ),
    }

    def crawl_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
        return pages[url]

    async with session_maker()() as session:
        source = await _queued_source(session, [HOME_URL])
        source.mode = "prefix"
        source.max_pages = 10
        await session.commit()
        source_id = source.id
        await ingest_source(session, source_id, fetch=crawl_fetch)

    async with session_maker()() as session:
        urls = set(
            (await session.scalars(select(KbPage.url).where(KbPage.source_id == source_id))).all()
        )
        assert urls == set(pages)


async def test_unexpected_page_exception_is_persisted_as_a_failed_job(
    migrated_db, monkeypatch
) -> None:
    def explode(*_args, **_kwargs):
        raise ValueError("broken extractor")

    monkeypatch.setattr("app.services.kb_pipeline.extract_html", explode)
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        source_id = source.id
        await ingest_source(session, source_id, fetch=fake_fetch)

    async with session_maker()() as session:
        page = await session.scalar(select(KbPage).where(KbPage.source_id == source_id))
        job = await session.scalar(select(KbPageJob).where(KbPageJob.source_id == source_id))
        source = await session.get(KbSource, source_id)
        assert page is not None and page.processing_status == "failed"
        assert job is not None and job.state == "dead_letter"
        assert job.last_error_code == "extract"
        assert source is not None and source.pages_failed == 1


async def test_failed_resync_does_not_replace_live_page_or_reenable_it(
    migrated_db, monkeypatch
) -> None:
    from app.services.kb_extract.types import EvidenceUnit

    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        source_id = source.id
        await ingest_source(session, source_id, fetch=fake_fetch)
        page = await session.scalar(select(KbPage).where(KbPage.source_id == source_id))
        assert page is not None
        original = (page.title, page.content_text, page.raw_html, page.content_sha256)
        page.enabled = False
        source.status = "queued"
        await session.commit()

        monkeypatch.setattr(
            "app.services.kb_pipeline.extract_html",
            lambda *_args, **_kwargs: [
                EvidenceUnit(
                    kind="section",
                    heading="Changed",
                    canonical_question=None,
                    answer_verbatim="Changed copy without the source fact.",
                    body_for_search="Changed copy without the source fact.",
                    display_locator=None,
                )
            ],
        )

        def changed_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
            return "<main><h1>Changed</h1><p>Delivery takes 99 days.</p></main>"

        await ingest_source(session, source_id, fetch=changed_fetch)

    async with session_maker()() as session:
        page = await session.scalar(select(KbPage).where(KbPage.source_id == source_id))
        source = await session.get(KbSource, source_id)
        assert page is not None
        assert source is not None and source.status == "failed"
        assert (page.title, page.content_text, page.raw_html, page.content_sha256) == original
        assert page.enabled is False
