import json
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


def _pending_page(page: KbPage, *, markdown: str, raw_html: str, content_text: str) -> dict:
    return {
        "page_id": page.id,
        "fetch_url": page.url,
        "digest": page.content_sha256 or "a" * 64,
        "token_estimate": 8,
        "title": page.title,
        "content_text": content_text,
        "display_locator": None,
        "raw_html": raw_html,
        "markdown": markdown,
        "http_status": 200,
    }


async def _running_source(session, *, start_url: str = FAQ_URL) -> tuple[KbSource, UUID]:
    site = await insert_site(session, f"easy-{uuid4().hex[:8]}", "SampleSite")
    site.allowed_origins = ["https://sample-site.example.com"]
    source = KbSource(
        site_id=site.id,
        start_url=start_url,
        mode="list",
        seed_urls=[start_url],
        status="running",
        stage="processing",
        embedder_id=configured_embedder_id(),
        enabled=True,
    )
    session.add(source)
    await session.flush()
    snapshot_id = await begin_snapshot(session, source.id)
    return source, snapshot_id


async def _add_page_with_chunk(
    session,
    source: KbSource,
    snapshot_id: UUID,
    *,
    url: str,
    title: str,
    answer: str,
    markdown: str | None,
) -> KbPage:
    page = KbPage(
        source_id=source.id,
        site_id=source.site_id,
        url=url,
        title=title,
        content_text=answer,
        content_sha256="a" * 64,
        http_status=200,
        enabled=True,
        raw_html=None,
        markdown=markdown,
    )
    session.add(page)
    await session.flush()
    session.add(
        KbChunk(
            page_id=page.id,
            site_id=source.site_id,
            snapshot_id=snapshot_id,
            ordinal=0,
            kind="faq",
            heading=title,
            canonical_question=title,
            answer_verbatim=answer,
            body=answer,
            aliases=[],
            enabled=True,
        )
    )
    await session.flush()
    return page


async def _running_source_with_chunk(session, *, answer: str, markdown: str | None):
    source, snapshot_id = await _running_source(session)
    page = await _add_page_with_chunk(
        session,
        source,
        snapshot_id,
        url=FAQ_URL,
        title="FAQs",
        answer=answer,
        markdown=markdown,
    )
    return snapshot_id, source, page


async def _running_source_with_two_chunks(session, *, timing_answer: str, pricing_answer: str):
    source, snapshot_id = await _running_source(session)
    timing = await _add_page_with_chunk(
        session,
        source,
        snapshot_id,
        url=FAQ_URL,
        title="Turnaround",
        answer=timing_answer,
        markdown=None,
    )
    pricing = await _add_page_with_chunk(
        session,
        source,
        snapshot_id,
        url="https://sample-site.example.com/pricing",
        title="Pricing",
        answer=pricing_answer,
        markdown=None,
    )
    return source, snapshot_id, timing, pricing


async def _snapshot_with_two_pages(
    session,
    *,
    timing_markdown: str,
    timing_answer: str,
    pricing_markdown: str,
    pricing_answer: str,
) -> UUID:
    source, snapshot_id = await _running_source(session)
    await _add_page_with_chunk(
        session,
        source,
        snapshot_id,
        url=FAQ_URL,
        title="Turnaround",
        answer=timing_answer,
        markdown=timing_markdown,
    )
    await _add_page_with_chunk(
        session,
        source,
        snapshot_id,
        url="https://sample-site.example.com/pricing",
        title="Pricing",
        answer=pricing_answer,
        markdown=pricing_markdown,
    )
    return snapshot_id


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
        candidate = await session.scalar(
            select(KbSnapshot).where(KbSnapshot.source_id == source_id, KbSnapshot.state == "live")
        )
        assert candidate is not None
        from app.services.kb_snapshot import promote

        await promote(session, candidate.id)
        await session.commit()

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


async def test_duplicate_answer_on_one_page_keeps_a_single_copy(migrated_db) -> None:
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
        remaining = list(
            (
                await session.scalars(
                    select(KbChunk.canonical_question).where(KbChunk.snapshot_id == snapshot_id)
                )
            ).all()
        )
        assert result.failed_rules == []
        assert snapshot.state == "validated"
        assert remaining == ["Q one?"]


async def _add_section_chunk(
    session,
    *,
    page: KbPage,
    snapshot_id: UUID,
    ordinal: int,
    heading: str,
    answer: str,
) -> None:
    session.add(
        KbChunk(
            page_id=page.id,
            site_id=page.site_id,
            snapshot_id=snapshot_id,
            ordinal=ordinal,
            kind="section",
            heading=heading,
            canonical_question=None,
            answer_verbatim=answer,
            body=f"{heading}\n{answer}",
            aliases=[],
            enabled=True,
        )
    )


async def test_shared_contact_block_is_kept_on_the_home_page(migrated_db) -> None:
    contact = "Phone: 202-555-0101. Email: inquiries@sample-data.example.com"
    mail_fact = "SampleMail verifies every address before the piece enters the mailstream."
    collection_fact = "Skip tracing covers nationwide addresses for collection agencies."
    async with session_maker()() as session:
        source, snapshot_id = await _running_source(
            session, start_url="https://sample-data.example.com/"
        )
        home = KbPage(
            source_id=source.id,
            site_id=source.site_id,
            url="https://sample-data.example.com/",
            title="Home",
            content_text=contact,
            content_sha256="e" * 64,
            http_status=200,
            enabled=True,
        )
        mail = KbPage(
            source_id=source.id,
            site_id=source.site_id,
            url="https://sample-data.example.com/samplemail",
            title="SampleMail",
            content_text=f"{mail_fact}\n{contact}",
            content_sha256="f" * 64,
            http_status=200,
            enabled=True,
        )
        collections = KbPage(
            source_id=source.id,
            site_id=source.site_id,
            url="https://sample-data.example.com/collections",
            title="Collections",
            content_text=f"{collection_fact}\n{contact}",
            content_sha256="c" * 64,
            http_status=200,
            enabled=True,
        )
        session.add_all([home, mail, collections])
        await session.flush()
        await _add_section_chunk(
            session,
            page=home,
            snapshot_id=snapshot_id,
            ordinal=0,
            heading="Contact",
            answer=contact,
        )
        await _add_section_chunk(
            session,
            page=mail,
            snapshot_id=snapshot_id,
            ordinal=0,
            heading="SampleMail",
            answer=mail_fact,
        )
        await _add_section_chunk(
            session,
            page=mail,
            snapshot_id=snapshot_id,
            ordinal=1,
            heading="Contact Information",
            answer=contact,
        )
        await _add_section_chunk(
            session,
            page=collections,
            snapshot_id=snapshot_id,
            ordinal=0,
            heading="Skip Tracing",
            answer=collection_fact,
        )
        await _add_section_chunk(
            session,
            page=collections,
            snapshot_id=snapshot_id,
            ordinal=1,
            heading="Contact Information",
            answer=contact,
        )
        await session.flush()
        result = await validate_snapshot(session, snapshot_id)
        remaining = list(
            (
                await session.execute(
                    select(KbChunk.heading, KbPage.url)
                    .join(KbPage, KbPage.id == KbChunk.page_id)
                    .where(KbChunk.snapshot_id == snapshot_id)
                    .order_by(KbPage.url, KbChunk.ordinal)
                )
            ).all()
        )
        assert result.failed_rules == []
        assert remaining == [
            ("Contact", "https://sample-data.example.com/"),
            ("Skip Tracing", "https://sample-data.example.com/collections"),
            ("SampleMail", "https://sample-data.example.com/samplemail"),
        ]
        contact_origins = (
            await session.execute(
                select(KbChunk.origin_urls)
                .join(KbPage, KbPage.id == KbChunk.page_id)
                .where(
                    KbChunk.snapshot_id == snapshot_id,
                    KbChunk.heading == "Contact",
                )
            )
        ).scalar_one()
        assert contact_origins == [
            "https://sample-data.example.com/",
            "https://sample-data.example.com/collections",
            "https://sample-data.example.com/samplemail",
        ]


async def test_second_source_does_not_keep_a_block_already_live_on_the_site(migrated_db) -> None:
    from app.services.kb_snapshot import promote

    contact = "Phone: 202-555-0101. Email: inquiries@sample-data.example.com"
    pasted = "Operators must refuse SSN, driver license, and medical details."
    async with session_maker()() as session:
        site = await insert_site(session, f"ds-{uuid4().hex[:8]}", "SampleData")
        website = KbSource(
            site_id=site.id,
            start_url="https://sample-data.example.com/",
            mode="list",
            seed_urls=["https://sample-data.example.com/"],
            status="running",
            stage="processing",
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add(website)
        await session.flush()
        live_id = await begin_snapshot(session, website.id)
        home = KbPage(
            source_id=website.id,
            site_id=site.id,
            url="https://sample-data.example.com/",
            title="Home",
            content_text=contact,
            content_sha256="a" * 64,
            http_status=200,
            enabled=True,
        )
        session.add(home)
        await session.flush()
        await _add_section_chunk(
            session, page=home, snapshot_id=live_id, ordinal=0, heading="Contact", answer=contact
        )
        await session.flush()
        await promote(session, live_id)
        notes = KbSource(
            site_id=site.id,
            start_url="text://operator-notes",
            mode="list",
            seed_urls=["text://operator-notes"],
            status="running",
            stage="processing",
            embedder_id=configured_embedder_id(),
            enabled=True,
            source_kind="text",
            display_name="Operator notes",
            manual_text=f"{pasted}\n{contact}",
        )
        session.add(notes)
        await session.flush()
        notes_id = await begin_snapshot(session, notes.id)
        notes_page = KbPage(
            source_id=notes.id,
            site_id=site.id,
            url="text://operator-notes",
            title="Operator notes",
            content_text=f"{pasted}\n{contact}",
            content_sha256="b" * 64,
            http_status=200,
            enabled=True,
        )
        session.add(notes_page)
        await session.flush()
        await _add_section_chunk(
            session,
            page=notes_page,
            snapshot_id=notes_id,
            ordinal=0,
            heading="PII refusal",
            answer=pasted,
        )
        await _add_section_chunk(
            session,
            page=notes_page,
            snapshot_id=notes_id,
            ordinal=1,
            heading="Contact Information",
            answer=contact,
        )
        await session.flush()
        result = await validate_snapshot(session, notes_id)
        remaining = list(
            (
                await session.scalars(
                    select(KbChunk.heading).where(KbChunk.snapshot_id == notes_id)
                )
            ).all()
        )
        assert result.failed_rules == []
        assert remaining == ["PII refusal"]


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


async def test_markdown_hour_range_missing_from_answers_does_not_fail_snapshot(migrated_db) -> None:
    html = "<html><head><style>.hero{width:100%}</style></head><body></body></html>"
    async with session_maker()() as session:
        snapshot_id = await _snapshot_with_page(
            session,
            raw_html=html,
            answer="Results are reported soon.",
            markdown="Most negative results are reported within 24-48 hours.",
        )
        result = await validate_snapshot(session, snapshot_id)
        bodies = list(
            (
                await session.scalars(
                    select(KbChunk.answer_verbatim).where(KbChunk.snapshot_id == snapshot_id)
                )
            ).all()
        )
        assert "numeric_fact_preservation" not in result.failed_rules
        assert bodies == ["Results are reported soon."]


async def test_en_dash_hour_range_matches_hyphen_in_answers(migrated_db) -> None:
    markdown = "Most negative results are reported within 24\u201348 hours."
    answer = "Most negative results are reported within 24-48 hours."
    async with session_maker()() as session:
        snapshot_id = await _snapshot_with_page(
            session, raw_html="<html><body></body></html>", answer=answer, markdown=markdown
        )
        result = await validate_snapshot(session, snapshot_id)
        snapshot = await session.get(KbSnapshot, snapshot_id)
        assert result.failed_rules == []
        assert snapshot is not None
        assert snapshot.state == "validated"


async def test_numeric_loss_on_one_page_keeps_the_other_page(migrated_db) -> None:
    timing_md = "Most negative results are reported within 24-48 hours."
    pricing_md = "Plans start at $1.49 per check."
    async with session_maker()() as session:
        snapshot_id = await _snapshot_with_two_pages(
            session,
            timing_markdown=timing_md,
            timing_answer=timing_md,
            pricing_markdown=pricing_md,
            pricing_answer="Contact us for pricing.",
        )
        result = await validate_snapshot(session, snapshot_id)
        snapshot = await session.get(KbSnapshot, snapshot_id)
        bodies = list(
            (
                await session.scalars(
                    select(KbChunk.answer_verbatim).where(KbChunk.snapshot_id == snapshot_id)
                )
            ).all()
        )
        assert result.failed_rules == []
        assert snapshot is not None
        assert snapshot.state == "validated"
        assert timing_md in bodies
        assert "Contact us for pricing." in bodies


async def test_failed_numeric_page_still_stores_crawled_markdown(migrated_db) -> None:
    from app.services.kb_pipeline import _finish_ingest

    html = "<html><body><main><p>Results are reported soon.</p></main></body></html>"
    markdown = "Most negative results are reported within 24-48 hours."
    async with session_maker()() as session:
        snapshot_id, source, page = await _running_source_with_chunk(
            session, answer="Results are reported soon.", markdown=None
        )
        page_id = page.id
        source_id = source.id
        await _finish_ingest(
            session,
            source,
            snapshot_id,
            [_pending_page(page, markdown=markdown, raw_html=html, content_text="soon.")],
        )

    async with session_maker()() as session:
        stored = await session.get(KbPage, page_id)
        source = await session.get(KbSource, source_id)
        assert stored is not None
        assert stored.markdown == markdown
        assert source is not None
        assert source.status == "ready"


async def test_numeric_loss_on_one_page_still_publishes_the_other(migrated_db) -> None:
    from app.services.kb_pipeline import _finish_ingest

    timing_md = "Most negative results are reported within 24-48 hours."
    pricing_md = "Plans start at $1.49 per check."
    async with session_maker()() as session:
        source, snapshot_id, timing, pricing = await _running_source_with_two_chunks(
            session,
            timing_answer=timing_md,
            pricing_answer="Contact us for pricing.",
        )
        source_id = source.id
        pricing_id = pricing.id
        await _finish_ingest(
            session,
            source,
            snapshot_id,
            [
                _pending_page(
                    timing, markdown=timing_md, raw_html="<p>ok</p>", content_text=timing_md
                ),
                _pending_page(
                    pricing,
                    markdown=pricing_md,
                    raw_html="<p>price</p>",
                    content_text="Contact us for pricing.",
                ),
            ],
        )

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        live_bodies = list(
            (
                await session.scalars(
                    select(KbChunk.answer_verbatim)
                    .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
                    .where(KbSnapshot.source_id == source_id, KbSnapshot.state == "live")
                )
            ).all()
        )
        pricing_page = await session.get(KbPage, pricing_id)
        assert source is not None
        assert source.status == "ready"
        assert timing_md in live_bodies
        assert "Contact us for pricing." in live_bodies
        assert pricing_page is not None
        assert pricing_page.markdown == pricing_md


async def test_faq_copy_disagreement_does_not_fail_snapshot_validation(migrated_db) -> None:
    html = """
    <html><body>
      <script type="application/ld+json">
        {"@type":"FAQPage","mainEntity":[{
          "@type":"Question",
          "name":"What are collection solutions?",
          "acceptedAnswer":{"@type":"Answer","text":"Collection solutions are data and outreach tools."}
        }]}
      </script>
      <main><p>Collection solutions are the data and outreach tools.</p></main>
    </body></html>
    """
    async with session_maker()() as session:
        snapshot_id = await _snapshot_with_page(
            session,
            raw_html=html,
            question="What are collection solutions?",
            answer="Collection solutions are the data and outreach tools.",
        )
        snapshot = await session.get(KbSnapshot, snapshot_id)
        result = await validate_snapshot(session, snapshot_id)

        assert result.failed_rules == []
        assert snapshot is not None
        assert snapshot.state == "validated"


async def test_long_jsonld_faq_persists_all_chunks(
    migrated_db,
) -> None:
    sentences = [
        f"Verification batch {index:03d} is checked against original records."
        for index in range(1, 61)
    ]
    answer = " ".join(sentences)
    payload = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "How are records checked?",
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
        ],
    }
    html = (
        "<html><body><script type='application/ld+json'>"
        f"{json.dumps(payload)}"
        "</script><main><h1>Record checks</h1><p>"
        f"{answer}"
        "</p></main></body></html>"
    )
    url = "https://sample-data.example.com/records"
    async with session_maker()() as session:
        site = await insert_site(session, f"data-{uuid4().hex[:8]}", "Sample Data Solutions")
        site.allowed_origins = ["https://sample-data.example.com"]
        source = KbSource(
            site_id=site.id,
            start_url=url,
            mode="list",
            seed_urls=[url],
            status="queued",
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add(source)
        await session.commit()
        source_id = source.id
        await ingest_source(session, source_id, fetch=_fetch(html))

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.status == "ready"
        faq_chunks = list(
            (
                await session.scalars(
                    select(KbChunk)
                    .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
                    .where(
                        KbSnapshot.source_id == source_id,
                        KbSnapshot.state == "live",
                        KbChunk.canonical_question == "How are records checked?",
                    )
                )
            ).all()
        )
        joined = " ".join(chunk.answer_verbatim for chunk in faq_chunks)
        assert len(faq_chunks) >= 2
        assert all(chunk.canonical_question == "How are records checked?" for chunk in faq_chunks)
        assert all(f"batch {index:03d}" in joined for index in range(1, 61))
        assert sum(len(chunk.answer_verbatim) for chunk in faq_chunks) >= 2500


async def test_privacy_policy_survives_unindexed_sidebar_percent(migrated_db) -> None:
    policy = (
        "We retain consumer report information for 7 years and dispose of it "
        "under FCRA secure destruction rules."
    )
    markdown = policy + "\n\nThis banner is shown to 100% of visitors."
    async with session_maker()() as session:
        snapshot_id = await _snapshot_with_page(
            session,
            raw_html="<html><body></body></html>",
            answer=policy,
            markdown=markdown,
        )
        result = await validate_snapshot(session, snapshot_id)
        bodies = list(
            (
                await session.scalars(
                    select(KbChunk.answer_verbatim).where(KbChunk.snapshot_id == snapshot_id)
                )
            ).all()
        )
        assert result.failed_rules == []
        assert bodies == [policy]


async def test_chunk_that_invents_a_turnaround_number_is_dropped(migrated_db) -> None:
    markdown = "Most negative results are reported within 24-48 hours."
    async with session_maker()() as session:
        snapshot_id = await _snapshot_with_page(
            session,
            raw_html="<html><body></body></html>",
            answer="Most negative results are reported within 17 minutes.",
            markdown=markdown,
        )
        result = await validate_snapshot(session, snapshot_id)
        chunk = await session.scalar(select(KbChunk).where(KbChunk.snapshot_id == snapshot_id))
        assert chunk is not None
        assert chunk.answer_verbatim == "Most negative results are reported within 17 minutes."
        assert chunk.enabled is False
        assert chunk.review_note == "unsupported_numeric_literal"
        assert "numeric_fact_preservation" in result.failed_rules
