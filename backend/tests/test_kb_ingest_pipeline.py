import asyncio
from uuid import uuid4

from sqlalchemy import func, select

from app.db import session_maker
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.repositories.kb_source_repo import KbSourceRepository
from app.services.full_context import load_live_units
from app.services.kb_embedder import FakeEmbedder, configured_embedder_id
from app.services.kb_hybrid import HybridKbSearch
from app.services.kb_ingest import canonical_url, ingest_source
from app.services.kb_source_admin import KbSourceService
from app.services.kb_validate import NUMERIC_RE
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


class _TextExtractClient:
    def __init__(self) -> None:
        self.structure_text_calls = 0
        self.received = None

    async def structure_text(self, title: str, body: str):
        from app.services.kb_page_structure import PageBlocks, StructuredPage, evidence_from_blocks

        self.structure_text_calls += 1
        self.received = (title, body)
        payload = PageBlocks.model_validate(
            {"blocks": [{"heading": title, "text": body, "tags": []}]}
        )
        return StructuredPage(evidence_from_blocks(payload, body, None))

    async def structure_page(self, *_args, **_kwargs):
        raise AssertionError("text sources must not use the crawl structurer")


async def test_text_source_uses_the_shared_pipeline_without_crawling(
    migrated_db, monkeypatch
) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, f"text-{uuid4().hex[:8]}", "Text knowledge")
        source = KbSource(
            site_id=site.id,
            start_url=f"kb-text://{uuid4()}",
            mode="list",
            seed_urls=[],
            status="queued",
            embedder_id=configured_embedder_id(),
            source_kind="text",
            display_name="Collections policy",
            manual_text="Payment plans are reviewed by the collections team.",
            enabled=True,
        )
        session.add(source)
        await session.commit()
        source_id = source.id

        def unexpected_fetch(*_args, **_kwargs):
            raise AssertionError("manual text must not enter the crawler")

        def unexpected_html_parser(*_args, **_kwargs):
            raise AssertionError("manual text must not use website extractors")

        llm = _TextExtractClient()
        monkeypatch.setattr("app.services.kb_pipeline.extract_html", unexpected_html_parser)
        await ingest_source(
            session,
            source_id,
            embedder=FakeEmbedder(),
            fetch=unexpected_fetch,
            llm_client=llm,
        )

        await session.refresh(source)
        page = await session.scalar(select(KbPage).where(KbPage.source_id == source_id))
        assert source.status == "ready"
        assert source.page_count == 1
        assert page is not None
        assert page.title == "Collections policy"
        assert page.citation_url is None
        assert llm.structure_text_calls == 1
        assert llm.received == (
            "Collections policy",
            "Payment plans are reviewed by the collections team.",
        )

        live_id = await session.scalar(
            select(KbSnapshot.id).where(
                KbSnapshot.source_id == source_id, KbSnapshot.state == "live"
            )
        )
        assert live_id is not None
        units = await load_live_units(session, [live_id])
        assert [unit.url for unit in units] == [""]
        live_text = page.content_text
        assert "Payment plans are reviewed by the collections team." in live_text

        patched = await KbSourceService(session).patch_source(
            source_id,
            enabled=None,
            body="Payment plans require manager approval.",
        )
        assert patched.status == "queued"
        assert (
            await session.scalar(
                select(KbSnapshot.id).where(
                    KbSnapshot.source_id == source_id, KbSnapshot.state == "live"
                )
            )
            == live_id
        )
        assert page.content_text == live_text


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


async def test_resync_reprocesses_live_sections_with_generated_question_aliases(
    migrated_db,
) -> None:
    from app.models.kb_snapshot import KbSnapshot

    embedder = CountingEmbedder()
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        source_id = source.id
        await ingest_source(session, source_id, embedder=embedder, fetch=fake_fetch)
        stale = await session.scalar(
            select(KbChunk)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .join(KbPage, KbPage.id == KbChunk.page_id)
            .where(KbPage.source_id == source_id, KbSnapshot.state == "live")
        )
        assert stale is not None
        stale.aliases = ["How fast is collection processing?"]
        source.status = "queued"
        await session.commit()

        await ingest_source(session, source_id, embedder=embedder, fetch=fake_fetch)

        live = await session.scalar(
            select(KbChunk)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .join(KbPage, KbPage.id == KbChunk.page_id)
            .where(KbPage.source_id == source_id, KbSnapshot.state == "live")
        )
        assert live is not None
        assert live.aliases == []
        assert embedder.document_calls == 2


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
    monkeypatch.setattr(kb_ingest_worker, "default_llm_client", lambda: None)
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
                    answer_verbatim="Changed copy promises results in 12 minutes.",
                    body_for_search="Changed copy promises results in 12 minutes.",
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


async def test_ingested_content_text_matches_live_chunk_answers(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        source_id = source.id
        await ingest_source(session, source_id, fetch=fake_fetch)
        page = await session.scalar(select(KbPage).where(KbPage.source_id == source_id))
        answers = list(
            (
                await session.scalars(
                    select(KbChunk.answer_verbatim)
                    .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
                    .where(
                        KbChunk.page_id == page.id,
                        KbSnapshot.state == "live",
                    )
                    .order_by(KbChunk.ordinal)
                )
            ).all()
        )
        assert page is not None
        assert answers
        assert page.content_text == "\n\n".join(answers)
        assert "24-48 hours" in page.content_text


DATA_HOME = "https://sample-data.example.com/"
DATA_PRODUCT = "https://sample-data.example.com/sampledata"
DATA_COLLECTIONS = "https://sample-data.example.com/collections"
DATA_MAIL = "https://sample-data.example.com/samplemail"
DATA_PRIVACY = "https://sample-data.example.com/privacy"
DATA_SALES = "https://sample-data.example.com/talk-to-sales"
DATA_PAGES = {
    DATA_HOME: (
        "<html><body><main><h1>Home</h1>"
        "<p>One data engine powers collections, verification, and mail services.</p>"
        "</main></body></html>"
    ),
    DATA_PRODUCT: (
        "<html><body><main>"
        "<h2>Identity verification</h2>"
        "<p>Identity verification checks submitted information against trusted records.</p>"
        "<h2>Outreach</h2>"
        "<p>Outreach services place calls only after skip tracing completes.</p>"
        "<h2>Locate</h2>"
        "<p>Updated phone and address information is located for right-party contact.</p>"
        "</main></body></html>"
    ),
    DATA_COLLECTIONS: (
        "<html><body><main>"
        "<h2>Skip tracing</h2>"
        "<p>Skip tracing covers nationwide addresses, scored phones, and right-party contact.</p>"
        "<h2>VPOE</h2>"
        "<p>VPOE confirms employment dates from the payroll source.</p>"
        "<h2>eVPOE</h2>"
        "<p>eVPOE returns the same employment record electronically.</p>"
        "</main></body></html>"
    ),
    DATA_MAIL: (
        "<html><body><main><h1>SampleMail</h1>"
        "<p>SampleMail verifies account ownership before a payment is submitted at $0.49.</p>"
        "</main></body></html>"
    ),
    DATA_PRIVACY: (
        "<html><body><main><h1>Privacy</h1>"
        "<p>We retain consumer report information for 7 years under FCRA rules.</p>"
        "</main></body></html>"
    ),
    DATA_SALES: (
        "<html><body><main><h1>Talk to sales</h1>"
        "<p>A scoped review starts within 24-48 hours of the first briefing.</p>"
        "</main></body></html>"
    ),
}
DATA_QUERIES = (
    ("data engine collections", "One data engine"),
    ("identity verification records", "submitted information"),
    ("outreach skip tracing", "Outreach services place calls"),
    ("skip tracing nationwide", "scored phones"),
    ("VPOE employment dates", "payroll source"),
    ("eVPOE electronically", "electronically"),
    ("SampleMail ownership", "account ownership"),
    ("retain consumer report", "7 years"),
    ("scoped review briefing", "24-48 hours"),
    ("phone and address information", "Updated phone and address"),
)


def _data_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
    return DATA_PAGES[url]


async def test_admin_sync_reingests_sampledata_fixture_pages(migrated_db) -> None:
    seed_urls = list(DATA_PAGES)
    async with session_maker()() as session:
        site = await insert_site(session, f"data-{uuid4().hex[:8]}", "Sample Data Solutions")
        site.allowed_origins = ["https://sample-data.example.com"]
        source = KbSource(
            site_id=site.id,
            start_url=DATA_HOME,
            mode="list",
            seed_urls=seed_urls,
            status="queued",
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add(source)
        await session.commit()
        source_id = source.id
        site_id = site.id
        await ingest_source(session, source_id, embedder=FakeEmbedder(), fetch=_data_fetch)
        await KbSourceService(session).sync_source(source_id)
        await ingest_source(session, source_id, embedder=FakeEmbedder(), fetch=_data_fetch)

    async with session_maker()() as session:
        pages = list(
            (await session.scalars(select(KbPage).where(KbPage.source_id == source_id))).all()
        )
        assert {page.url for page in pages} == set(seed_urls)
        for page in pages:
            answers = list(
                (
                    await session.scalars(
                        select(KbChunk.answer_verbatim)
                        .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
                        .where(
                            KbChunk.page_id == page.id,
                            KbSnapshot.state == "live",
                        )
                        .order_by(KbChunk.ordinal)
                    )
                ).all()
            )
            assert answers
            assert page.content_text == "\n\n".join(answers)
            source_copy = page.markdown or page.content_text
            for match in NUMERIC_RE.finditer(source_copy):
                assert any(match.group(0) in answer for answer in answers)
        search = HybridKbSearch(session)
        for query, literal in DATA_QUERIES:
            hits = await search.search(site_id, query, query_vector=None)
            assert any(literal in (hit.answer_verbatim or hit.body) for hit in hits), query
        overview = await search.search(site_id, "what services do you offer", query_vector=None)
        assert len(overview) >= 3
