from app.services.kb_extract.types import EvidenceUnit
from app.services.kb_llm_extract import apply_cleaner, clean_section_local

SKIP_TRACE = "Skip tracing covers nationwide addresses, scored phones, and right-party contact."


def test_local_cleaner_strips_cta_and_arrows_but_keeps_numbers() -> None:
    cleaned = clean_section_local(
        "Turnaround",
        "Most negative results are reported within 24-48 hours. →\nView\nLearn more",
    )
    assert cleaned == "Most negative results are reported within 24-48 hours."


def test_apply_cleaner_keeps_full_section_instead_of_page_digest() -> None:
    section = EvidenceUnit(
        kind="section",
        heading="Skip tracing",
        canonical_question=None,
        answer_verbatim=SKIP_TRACE,
        body_for_search=f"Skip tracing\n{SKIP_TRACE}",
        display_locator=None,
    )
    digest = EvidenceUnit(
        kind="fact",
        heading="product",
        canonical_question=None,
        answer_verbatim="Collection solutions are the data, verification, and outreach tools.",
        body_for_search="product\nCollection solutions are the data, verification, and outreach tools.",
        display_locator=None,
        topic="product",
    )

    kept = apply_cleaner([section, digest])

    answers = [unit.answer_verbatim for unit in kept]
    assert SKIP_TRACE in answers
    assert "right-party contact" in " ".join(answers)


def test_apply_cleaner_drops_pure_chrome_section() -> None:
    chrome = EvidenceUnit(
        kind="section",
        heading="Collection",
        canonical_question=None,
        answer_verbatim="View",
        body_for_search="Collection\nView",
        display_locator=None,
    )
    assert apply_cleaner([chrome]) == []


def test_local_cleanup_keeps_cookie_policy_facts() -> None:
    assert clean_section_local("Privacy", "We do not use cookies for advertising.") == (
        "We do not use cookies for advertising."
    )


async def test_structure_units_cache_skips_second_client_call(migrated_db) -> None:
    from uuid import uuid4

    from app.db import session_maker
    from app.models.kb_page import KbPage
    from app.models.kb_source import KbSource
    from app.services.kb_embedder import configured_embedder_id
    from app.services.kb_page_structure import PageBlocks, StructuredPage, evidence_from_blocks
    from app.services.kb_pipeline import _clean_units
    from tests.bot_fixtures import insert_site

    answer = "Most negative results are reported within 24-48 hours."

    class CountingClient:
        calls = 0
        model = "test-page-structurer"

        async def structure_page(self, url, title, text, metadata=None):
            del title, metadata
            CountingClient.calls += 1
            payload = PageBlocks.model_validate(
                {"blocks": [{"heading": "Turnaround", "text": answer, "tags": []}]}
            )
            return StructuredPage(evidence_from_blocks(payload, text, url))

    digest = "b" * 64
    async with session_maker()() as session:
        site = await insert_site(session, f"easy-{uuid4().hex[:8]}", "SampleSite")
        source = KbSource(
            site_id=site.id,
            start_url="https://sample-site.example.com/faq",
            mode="list",
            seed_urls=["https://sample-site.example.com/faq"],
            status="ready",
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add(source)
        await session.flush()
        page = KbPage(
            source_id=source.id,
            site_id=site.id,
            url="https://sample-site.example.com/faq",
            title="Turnaround",
            content_text=answer,
            content_sha256=digest,
            http_status=200,
            enabled=True,
        )
        session.add(page)
        await session.flush()
        first = await _clean_units(
            session,
            page,
            digest,
            [],
            CountingClient(),
            crawl_text=answer,
            crawl_title="Turnaround",
        )
        second = await _clean_units(
            session,
            page,
            digest,
            [],
            CountingClient(),
            crawl_text=answer,
            crawl_title="Turnaround",
        )
        await session.commit()

    assert CountingClient.calls == 1
    assert first[0].answer_verbatim == answer
    assert second[0].answer_verbatim == first[0].answer_verbatim
