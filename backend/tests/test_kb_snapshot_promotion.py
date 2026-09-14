from uuid import uuid4

from sqlalchemy import select

from app.db import session_maker
from app.models.kb_chunk import KbChunk
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.kb_embedder import FakeEmbedder, configured_embedder_id
from app.services.kb_ingest import ingest_source
from app.services.kb_snapshot import begin_snapshot, fail, promote, validate_snapshot
from app.services.kb_validate import ValidationResult
from tests.bot_fixtures import insert_site

FAQ_URL = "https://sample-site.example.com/faq"
TIMING_HTML = (
    "<html><body><main><h1>Turnaround</h1>"
    "<p>Most negative results are reported within 24-48 hours.</p></main></body></html>"
)
DOT_HTML = (
    "<html><body><main><h1>DOT</h1>"
    "<p>DOT-regulated testing follows federal rules for prohibited substances.</p>"
    "</main></body></html>"
)


def _fetch(pages: dict[str, str]):
    def fake_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
        if url not in pages:
            from app.services.kb_crawl import FetchError

            raise FetchError("timeout")
        return pages[url]

    return fake_fetch


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


async def _live_question(session, source_id) -> list[str]:
    result = await session.execute(
        select(KbChunk.canonical_question)
        .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
        .where(KbSnapshot.source_id == source_id, KbSnapshot.state == "live")
    )
    return [row for row in result.scalars().all() if row]


async def test_promote_replaces_live_snapshot_and_failed_validate_keeps_previous(
    migrated_db,
) -> None:
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        first = await begin_snapshot(session, source.id)
        first_row = await session.get(KbSnapshot, first)
        assert first_row is not None
        first_row.token_estimate = 12
        first_row.content_hash = "a" * 64
        result = await validate_snapshot(session, first)
        assert result.failed_rules == []
        await promote(session, first)
        await session.commit()

        second = await begin_snapshot(session, source.id)
        second_row = await session.get(KbSnapshot, second)
        assert second_row is not None
        second_row.token_estimate = 20
        second_row.content_hash = "b" * 64
        await validate_snapshot(session, second)
        await promote(session, second)
        await session.commit()
        first_row = await session.get(KbSnapshot, first)
        second_row = await session.get(KbSnapshot, second)
        assert first_row is not None and first_row.state == "superseded"
        assert second_row is not None and second_row.state == "live"

        third = await begin_snapshot(session, source.id)
        await fail(session, third, "validation")
        await session.commit()
        third_row = await session.get(KbSnapshot, third)
        second_row = await session.get(KbSnapshot, second)
        assert third_row is not None and third_row.state == "failed"
        assert second_row is not None and second_row.state == "live"


async def test_mid_run_fetch_error_leaves_previous_live_snapshot(migrated_db) -> None:
    embedder = FakeEmbedder()
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        source_id = source.id
        await ingest_source(
            session, source_id, embedder=embedder, fetch=_fetch({FAQ_URL: TIMING_HTML})
        )
        candidate = await session.scalar(
            select(KbSnapshot).where(KbSnapshot.source_id == source_id, KbSnapshot.state == "live")
        )
        assert candidate is not None
        await promote(session, candidate.id)
        await session.commit()

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "ready"
        live_before = await session.scalars(
            select(KbSnapshot.id).where(
                KbSnapshot.source_id == source_id, KbSnapshot.state == "live"
            )
        )
        live_ids = list(live_before)
        assert len(live_ids) == 1
        source.status = "queued"
        await session.commit()

        def boom(url: str, _hosts: set[str], hops: int = 0) -> str:
            from app.services.kb_crawl import FetchError

            raise FetchError("timeout")

        await ingest_source(session, source_id, embedder=embedder, fetch=boom)

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        live = (
            await session.scalars(
                select(KbSnapshot).where(
                    KbSnapshot.source_id == source_id, KbSnapshot.state == "live"
                )
            )
        ).all()
        assert len(live) == 1
        assert live[0].id == live_ids[0]
        bodies = await session.scalars(
            select(KbChunk.body)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .where(KbSnapshot.state == "live", KbSnapshot.source_id == source_id)
        )
        assert any("24-48 hours" in body for body in bodies)


async def test_validate_snapshot_returns_typed_result(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        snapshot_id = await begin_snapshot(session, source.id)
        result = await validate_snapshot(session, snapshot_id)
        assert isinstance(result, ValidationResult)
