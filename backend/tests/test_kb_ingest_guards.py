from uuid import uuid4

from sqlalchemy import select

from app.db import session_maker
from app.models.kb_page import KbPage
from app.models.kb_source import KbSource
from app.services.kb_embedder import configured_embedder_id
from app.services.kb_ingest import ingest_source
from tests.bot_fixtures import insert_site

ROOT_URL = "https://sample-site.example.com/"
FAQ_URL = "https://sample-site.example.com/faq"
DOT_URL = "https://sample-site.example.com/dot"
A_URL = "https://sample-site.example.com/a"
AB_URL = "https://sample-site.example.com/a/b"
FOO_URL = "https://sample-site.example.com/foo"
FOOBAR_URL = "https://sample-site.example.com/foobar"
ROBOTS_URL = "https://sample-site.example.com/robots.txt"

FAQ_HTML = (
    "<html><body><main><h1>FAQ</h1>"
    "<p>Most negative results are reported within 24-48 hours.</p>"
    "<a href='/dot'>DOT</a></main></body></html>"
)
DOT_HTML = (
    "<html><body><main><h1>DOT</h1>"
    "<p>DOT-regulated testing follows federal rules.</p></main></body></html>"
)
ROOT_HTML = (
    "<html><body><main><h1>Root</h1><a href='/a'>A</a><a href='/a/b'>AB</a></main></body></html>"
)
A_HTML = "<html><body><main><h1>A</h1><p>Depth one.</p><a href='/a/b'>AB</a></main></body></html>"
AB_HTML = "<html><body><main><h1>AB</h1><p>Depth two.</p></main></body></html>"
FOO_HTML = (
    "<html><body><main><h1>Foo</h1>"
    "<p>Prefix start.</p><a href='/foobar'>Foobar</a></main></body></html>"
)
FOOBAR_HTML = "<html><body><main><h1>Foobar</h1><p>Should not crawl.</p></main></body></html>"
ROBOTS_BLOCK_FAQ = "User-agent: *\nDisallow: /faq\n"


async def _source(
    session,
    *,
    mode: str = "prefix",
    start_url: str = ROOT_URL,
    seed_urls: list[str] | None = None,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
    max_depth: int = 3,
) -> KbSource:
    site = await insert_site(session, f"easy-{uuid4().hex[:8]}", "SampleSite")
    site.allowed_origins = ["https://sample-site.example.com"]
    source = KbSource(
        site_id=site.id,
        start_url=start_url,
        mode=mode,
        seed_urls=seed_urls or [start_url],
        include_globs=include_globs or [],
        exclude_globs=exclude_globs or [],
        max_depth=max_depth,
        status="queued",
        embedder_id=configured_embedder_id(),
        enabled=True,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


def _pages_fetch(pages: dict[str, str], robots_body: str | None = None):
    def fake_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
        if url == ROBOTS_URL and robots_body is not None:
            return robots_body
        if url not in pages:
            from app.services.kb_crawl import FetchError

            raise FetchError("http")
        return pages[url]

    return fake_fetch


async def test_robots_disallow_skips_page(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _source(session, mode="list", start_url=FAQ_URL, seed_urls=[FAQ_URL])
        source_id = source.id
        await ingest_source(
            session,
            source_id,
            fetch=_pages_fetch({FAQ_URL: FAQ_HTML}, robots_body=ROBOTS_BLOCK_FAQ),
        )

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "failed"
        assert source.error_code == "empty"


async def test_max_depth_limits_discovered_links(migrated_db) -> None:
    pages = {
        ROOT_URL: ROOT_HTML,
        A_URL: A_HTML,
        AB_URL: AB_HTML,
    }
    async with session_maker()() as session:
        source = await _source(session, max_depth=1)
        source_id = source.id
        await ingest_source(session, source_id, fetch=_pages_fetch(pages))

    async with session_maker()() as session:
        urls = (
            await session.scalars(select(KbPage.url).where(KbPage.source_id == source_id))
        ).all()
        assert ROOT_URL in urls
        assert A_URL in urls
        assert AB_URL not in urls


async def test_include_glob_filters_crawled_paths(migrated_db) -> None:
    pages = {FAQ_URL: FAQ_HTML, DOT_URL: DOT_HTML}
    async with session_maker()() as session:
        source = await _source(
            session,
            mode="list",
            start_url=FAQ_URL,
            seed_urls=[FAQ_URL, DOT_URL],
            include_globs=["/faq*"],
        )
        source_id = source.id
        await ingest_source(session, source_id, fetch=_pages_fetch(pages))

    async with session_maker()() as session:
        urls = (
            await session.scalars(select(KbPage.url).where(KbPage.source_id == source_id))
        ).all()
        assert urls == [FAQ_URL]


async def test_exclude_glob_skips_matching_paths(migrated_db) -> None:
    pages = {FAQ_URL: FAQ_HTML, DOT_URL: DOT_HTML}
    async with session_maker()() as session:
        source = await _source(
            session,
            mode="list",
            start_url=FAQ_URL,
            seed_urls=[FAQ_URL, DOT_URL],
            exclude_globs=["/dot*"],
        )
        source_id = source.id
        await ingest_source(session, source_id, fetch=_pages_fetch(pages))

    async with session_maker()() as session:
        urls = (
            await session.scalars(select(KbPage.url).where(KbPage.source_id == source_id))
        ).all()
        assert FAQ_URL in urls
        assert DOT_URL not in urls


async def test_prefix_boundary_does_not_match_foobar(migrated_db) -> None:
    pages = {
        FOO_URL: FOO_HTML,
        FOOBAR_URL: FOOBAR_HTML,
    }
    async with session_maker()() as session:
        source = await _source(session, start_url=FOO_URL)
        source_id = source.id
        await ingest_source(session, source_id, fetch=_pages_fetch(pages))

    async with session_maker()() as session:
        urls = (
            await session.scalars(select(KbPage.url).where(KbPage.source_id == source_id))
        ).all()
        assert FOOBAR_URL not in urls
