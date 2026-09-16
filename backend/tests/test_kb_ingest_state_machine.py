from uuid import uuid4

from sqlalchemy import func, select

from app.db import session_maker
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.repositories.kb_page_job_repo import KbPageJobRepository
from app.services.kb_crawl import FetchError
from app.services.kb_embedder import FakeEmbedder, configured_embedder_id
from app.services.kb_ingest import ingest_source
from tests.bot_fixtures import insert_site

FAQ_URL = "https://sample-site.example.com/faq"
DOT_URL = "https://sample-site.example.com/dot"
PRICE_URL = "https://sample-site.example.com/pricing"
FAQ_HTML = (
    "<html><body><main><h1>Turnaround</h1>"
    "<p>Most negative results are reported within 24-48 hours.</p></main></body></html>"
)
DOT_HTML = (
    "<html><body><main><h1>DOT</h1>"
    "<p>DOT-regulated testing follows federal rules for prohibited substances.</p>"
    "</main></body></html>"
)
PRICE_HTML = (
    "<html><body><main><h1>Pricing</h1>"
    "<p>Panel pricing is quoted per package.</p></main></body></html>"
)
SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://sample-site.example.com/faq</loc></url>
  <url><loc>https://sample-site.example.com/dot</loc></url>
</urlset>
"""
PAGES = {
    FAQ_URL: FAQ_HTML,
    DOT_URL: DOT_HTML,
    PRICE_URL: PRICE_HTML,
    "https://sample-site.example.com/sitemap.xml": SITEMAP,
}


async def _source(session, urls: list[str], mode: str = "list") -> KbSource:
    site = await insert_site(session, f"easy-{uuid4().hex[:8]}", "SampleSite")
    site.allowed_origins = ["https://sample-site.example.com"]
    source = KbSource(
        site_id=site.id,
        start_url=urls[0],
        mode=mode,
        seed_urls=urls,
        status="queued",
        embedder_id=configured_embedder_id(),
        enabled=True,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


def _fetch(pages: dict[str, str]):
    def fake(url: str, _hosts: set[str], hops: int = 0) -> str:
        if url not in pages:
            raise FetchError("http")
        return pages[url]

    return fake


async def test_duplicate_canonical_urls_collapse_to_one_page(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _source(session, [FAQ_URL, FAQ_URL + "#timing"])
        await ingest_source(session, source.id, embedder=FakeEmbedder(), fetch=_fetch(PAGES))
        source_id = source.id

    async with session_maker()() as session:
        count = await session.scalar(
            select(func.count()).select_from(KbPage).where(KbPage.source_id == source_id)
        )
        assert count == 1


async def test_hash_faq_anchor_is_not_a_second_page(migrated_db) -> None:
    home = (
        "<html><body><main><h1>Home</h1>"
        "<p>Most negative results are reported within 24-48 hours.</p>"
        "<a href='#faq'>FAQ</a></main></body></html>"
    )
    pages = {
        "https://sample-site.example.com/": home,
        "https://sample-site.example.com/sitemap.xml": "",
    }
    async with session_maker()() as session:
        source = await _source(session, ["https://sample-site.example.com/"], mode="prefix")
        await ingest_source(session, source.id, embedder=FakeEmbedder(), fetch=_fetch(pages))
        source_id = source.id

    async with session_maker()() as session:
        urls = list(
            (await session.scalars(select(KbPage.url).where(KbPage.source_id == source_id))).all()
        )
        assert urls == ["https://sample-site.example.com/"]


async def test_http_failure_on_one_page_does_not_drop_siblings(migrated_db) -> None:
    pages = dict(PAGES)

    def fake(url: str, _hosts: set[str], hops: int = 0) -> str:
        if url == DOT_URL:
            raise FetchError("http")
        if url not in pages:
            raise FetchError("http")
        return pages[url]

    async with session_maker()() as session:
        source = await _source(session, [FAQ_URL, DOT_URL, PRICE_URL])
        await ingest_source(session, source.id, embedder=FakeEmbedder(), fetch=fake)
        source_id = source.id

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "ready"
        assert source.pages_failed == 1
        urls = set(
            (await session.scalars(select(KbPage.url).where(KbPage.source_id == source_id))).all()
        )
        assert FAQ_URL in urls
        assert PRICE_URL in urls
        failed = await session.scalar(
            select(KbPage).where(KbPage.source_id == source_id, KbPage.url == DOT_URL)
        )
        assert failed is not None
        assert failed.processing_status == "failed"
        job = await session.scalar(
            select(KbPageJob).where(
                KbPageJob.page_id == failed.id, KbPageJob.state == "dead_letter"
            )
        )
        assert job is not None
        assert job.attempts == 5
        live_chunks = await session.scalar(
            select(func.count())
            .select_from(KbChunk)
            .join(KbPage, KbChunk.page_id == KbPage.id)
            .where(KbPage.source_id == source_id, KbPage.url.in_([FAQ_URL, PRICE_URL]))
        )
        assert live_chunks == 2


async def test_unchanged_recrawl_skips_embed_and_counts_skip(migrated_db) -> None:
    embedder = FakeEmbedder()
    calls = {"n": 0}
    original = embedder.embed_documents

    async def counted(texts: list[str]) -> list[list[float]]:
        calls["n"] += 1
        return await original(texts)

    embedder.embed_documents = counted  # type: ignore[method-assign]
    async with session_maker()() as session:
        source = await _source(session, [FAQ_URL, DOT_URL])
        source_id = source.id
        await ingest_source(session, source_id, embedder=embedder, fetch=_fetch(PAGES))
        first = calls["n"]
        source.status = "queued"
        await session.commit()
        await ingest_source(session, source_id, embedder=embedder, fetch=_fetch(PAGES))

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "ready"
        assert source.pages_skipped_unchanged == 2
        assert calls["n"] == first
        unchanged = list(
            (
                await session.scalars(
                    select(KbSnapshot).where(
                        KbSnapshot.source_id == source_id,
                        KbSnapshot.state == "unchanged",
                    )
                )
            ).all()
        )
        assert len(unchanged) == 1
        jobs = list(
            (
                await session.scalars(
                    select(KbPageJob).where(KbPageJob.snapshot_id == unchanged[0].id)
                )
            ).all()
        )
        assert len(jobs) == 2
        assert all(job.renderer == "injected" for job in jobs)
        assert all(job.events for job in jobs)


async def test_failed_page_on_resync_keeps_its_previous_live_chunks(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _source(session, [FAQ_URL, DOT_URL])
        source_id = source.id
        await ingest_source(session, source_id, embedder=FakeEmbedder(), fetch=_fetch(PAGES))
        source.status = "queued"
        await session.commit()

        def partial_fetch(url: str, hosts: set[str], hops: int = 0) -> str:
            if url == DOT_URL:
                raise FetchError("timeout")
            return _fetch(PAGES)(url, hosts, hops)

        await ingest_source(session, source_id, embedder=FakeEmbedder(), fetch=partial_fetch)

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "ready"
        assert source.pages_failed == 1
        assert source.page_count == 2
        live_answers = set(
            (
                await session.scalars(
                    select(KbChunk.answer_verbatim)
                    .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
                    .where(
                        KbSnapshot.source_id == source_id,
                        KbSnapshot.state == "live",
                    )
                )
            ).all()
        )
        assert (
            "DOT-regulated testing follows federal rules for prohibited substances." in live_answers
        )


async def test_single_page_retry_fetches_only_that_page_and_keeps_other_live_pages(
    migrated_db,
) -> None:
    updated_dot = (
        "<html><body><main><h1>DOT</h1>"
        "<p>DOT testing follows updated federal collection rules.</p>"
        "</main></body></html>"
    )
    fetched: list[str] = []

    def retry_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
        if url.endswith("/robots.txt"):
            raise KeyError(url)
        fetched.append(url)
        if url != DOT_URL:
            raise AssertionError(f"unexpected page fetch: {url}")
        return updated_dot

    async with session_maker()() as session:
        source = await _source(session, [FAQ_URL, DOT_URL])
        source_id = source.id
        await ingest_source(session, source_id, embedder=FakeEmbedder(), fetch=_fetch(PAGES))
        source.retry_urls = [DOT_URL]
        source.status = "queued"
        await session.commit()
        await ingest_source(session, source_id, embedder=FakeEmbedder(), fetch=retry_fetch)

    assert fetched == [DOT_URL]
    async with session_maker()() as session:
        live_answers = set(
            (
                await session.scalars(
                    select(KbChunk.answer_verbatim)
                    .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
                    .where(
                        KbSnapshot.source_id == source_id,
                        KbSnapshot.state == "live",
                    )
                )
            ).all()
        )
        assert "Most negative results are reported within 24-48 hours." in live_answers
        assert "DOT testing follows updated federal collection rules." in live_answers


async def test_prefix_sitemap_supplies_url_list(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _source(session, ["https://sample-site.example.com/"], mode="prefix")
        await ingest_source(session, source.id, embedder=FakeEmbedder(), fetch=_fetch(PAGES))
        source_id = source.id

    async with session_maker()() as session:
        urls = set(
            (await session.scalars(select(KbPage.url).where(KbPage.source_id == source_id))).all()
        )
        assert FAQ_URL in urls
        assert DOT_URL in urls
        assert PRICE_URL not in urls


async def test_stuck_running_job_is_reset_to_pending(migrated_db) -> None:
    from datetime import UTC, datetime, timedelta

    async with session_maker()() as session:
        source = await _source(session, [FAQ_URL])
        await ingest_source(session, source.id, embedder=FakeEmbedder(), fetch=_fetch(PAGES))
        job = await session.scalar(select(KbPageJob).limit(1))
        assert job is not None
        job.state = "running"
        job.started_at = datetime.now(UTC) - timedelta(minutes=11)
        job.attempts = 1
        await session.commit()
        job_id = job.id
        reset = await KbPageJobRepository(session).reap_stuck()
        await session.commit()

    async with session_maker()() as session:
        job = await session.get(KbPageJob, job_id)
        assert reset == 1
        assert job is not None
        assert job.state == "pending"
        assert job.attempts == 2
