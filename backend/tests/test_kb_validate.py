from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select

from app.db import session_maker
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_smoke_assertion import KbSmokeAssertion
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.kb_embedder import configured_embedder_id
from app.services.kb_ingest import ingest_source
from app.services.kb_snapshot import begin_snapshot
from app.services.kb_validate import validate_snapshot
from tests.bot_fixtures import insert_site

FAQ_URL = "https://sample-site.example.com/faq"
FAQ_HTML = (Path(__file__).parent / "fixtures" / "kb" / "samplesite_faq.html").read_text()
MISSING_MRO_HTML = """
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "How quickly are drug screening results available?",
    "acceptedAnswer": {"@type": "Answer", "text": "Results are reported soon."}
  }]
}
</script>
<main><h1>FAQs</h1><p>Results are reported soon.</p></main>
</body></html>
"""


def _fetch(html: str):
    def fake_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
        return html

    return fake_fetch


async def _source_with_smoke(session, html_url: str = FAQ_URL) -> KbSource:
    site = await insert_site(session, f"easy-{uuid4().hex[:8]}", "SampleSite")
    site.allowed_origins = ["https://sample-site.example.com"]
    source = KbSource(
        site_id=site.id,
        start_url=html_url,
        mode="list",
        seed_urls=[html_url],
        status="queued",
        embedder_id=configured_embedder_id(),
        enabled=True,
    )
    session.add(source)
    await session.flush()
    session.add(
        KbSmokeAssertion(
            source_id=source.id,
            must_include=["24-48", "MRO", "rapid"],
            must_exclude=[],
        )
    )
    await session.commit()
    await session.refresh(source)
    return source


async def _snapshot_with_page(
    session,
    *,
    raw_html: str,
    answer: str,
    markdown: str | None = None,
    question: str = "How quickly are results available?",
) -> UUID:
    site = await insert_site(session, f"easy-{uuid4().hex[:8]}", "SampleSite")
    site.allowed_origins = ["https://sample-site.example.com"]
    source = KbSource(
        site_id=site.id,
        start_url=FAQ_URL,
        mode="list",
        seed_urls=[FAQ_URL],
        status="running",
        embedder_id=configured_embedder_id(),
        enabled=True,
    )
    session.add(source)
    await session.flush()
    snapshot_id = await begin_snapshot(session, source.id)
    page = KbPage(
        source_id=source.id,
        site_id=site.id,
        url=FAQ_URL,
        title="FAQs",
        content_text=answer,
        content_sha256="a" * 64,
        http_status=200,
        enabled=True,
        raw_html=raw_html,
        markdown=markdown,
    )
    session.add(page)
    await session.flush()
    session.add(
        KbChunk(
            page_id=page.id,
            site_id=site.id,
            snapshot_id=snapshot_id,
            ordinal=0,
            kind="faq",
            heading=question,
            canonical_question=question,
            answer_verbatim=answer,
            body=answer,
            aliases=[],
            enabled=True,
        )
    )
    await session.flush()
    return snapshot_id


async def test_missing_numeric_literal_fails_validation_and_keeps_previous_live(
    migrated_db,
) -> None:
    async with session_maker()() as session:
        source = await _source_with_smoke(session)
        source_id = source.id
        await ingest_source(session, source_id, fetch=_fetch(FAQ_HTML))

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "ready"
        live = await session.scalar(
            select(KbSnapshot.id).where(
                KbSnapshot.source_id == source_id, KbSnapshot.state == "live"
            )
        )
        source.status = "queued"
        await session.commit()
        await ingest_source(session, source_id, fetch=_fetch(MISSING_MRO_HTML))

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "failed"
        assert source.error_code == "validation"
        still_live = await session.scalar(
            select(KbSnapshot.id).where(
                KbSnapshot.source_id == source_id, KbSnapshot.state == "live"
            )
        )
        assert still_live == live
        questions = (
            await session.scalars(
                select(KbChunk.canonical_question)
                .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
                .where(KbSnapshot.state == "live", KbSnapshot.source_id == source_id)
            )
        ).all()
        assert "How quickly are drug screening results available?" in questions


async def test_duplicate_answer_hash_fails_dedupe(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _source_with_smoke(session)
        snapshot_id = await begin_snapshot(session, source.id)
        snapshot = await session.get(KbSnapshot, snapshot_id)
        assert snapshot is not None
        page = KbPage(
            source_id=source.id,
            site_id=source.site_id,
            url=FAQ_URL,
            title="FAQs",
            content_text="Most negative results are reported within 24-48 hours.",
            content_sha256="d" * 64,
            http_status=200,
            enabled=True,
            raw_html=FAQ_HTML,
        )
        session.add(page)
        await session.flush()
        shared = "Most negative results are reported within 24-48 hours, rapid MRO."
        for ordinal, question in enumerate(("Q one?", "Q two?")):
            session.add(
                KbChunk(
                    page_id=page.id,
                    site_id=source.site_id,
                    snapshot_id=snapshot_id,
                    ordinal=ordinal,
                    kind="faq",
                    heading=question,
                    canonical_question=question,
                    answer_verbatim=shared,
                    body=shared,
                    aliases=[],
                    enabled=True,
                )
            )
        await session.flush()
        result = await validate_snapshot(session, snapshot_id)
        assert "dedupe" in result.failed_rules
        assert snapshot.state == "failed"


async def test_smoke_assertion_missing_mro_blocks_promote(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _source_with_smoke(session)
        source_id = source.id
        await ingest_source(session, source_id, fetch=_fetch(MISSING_MRO_HTML))

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "failed"
        assert source.error_code == "validation"
        live = await session.scalar(
            select(KbSnapshot.id).where(
                KbSnapshot.source_id == source_id, KbSnapshot.state == "live"
            )
        )
        assert live is None


async def test_passing_smoke_snapshot_promotes(migrated_db) -> None:
    async with session_maker()() as session:
        source = await _source_with_smoke(session)
        source_id = source.id
        await ingest_source(session, source_id, fetch=_fetch(FAQ_HTML))

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "ready"
        live = await session.scalar(
            select(KbSnapshot.state).where(
                KbSnapshot.source_id == source_id, KbSnapshot.state == "live"
            )
        )
        assert live == "live"


async def test_stylesheet_percentages_do_not_fail_numeric_preservation(migrated_db) -> None:
    html = (
        "<html><head><style>.hero{width:100%;transform:scale(200%);opacity:0%}</style></head>"
        "<body></body></html>"
    )
    markdown = "Most negative results are reported within 24-48 hours."
    async with session_maker()() as session:
        snapshot_id = await _snapshot_with_page(
            session, raw_html=html, answer=markdown, markdown=markdown
        )
        result = await validate_snapshot(session, snapshot_id)
        assert "numeric_fact_preservation" not in result.failed_rules


async def test_markdown_hour_range_missing_from_answers_fails_numeric(migrated_db) -> None:
    html = "<html><head><style>.hero{width:100%}</style></head><body></body></html>"
    async with session_maker()() as session:
        snapshot_id = await _snapshot_with_page(
            session,
            raw_html=html,
            answer="Results are reported soon.",
            markdown="Most negative results are reported within 24-48 hours.",
        )
        result = await validate_snapshot(session, snapshot_id)
        assert "numeric_fact_preservation" in result.failed_rules
