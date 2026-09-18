from app.services.kb_chunk import pack_chunks
from app.services.kb_extract.types import EvidenceUnit
from app.services.kb_page_structure import (
    HaikuPageStructurer,
    PageBlocks,
    evidence_from_blocks,
    page_blocks_from_proposal,
    page_windows,
    unique_units,
)
from app.settings import get_settings

SOURCE = "Prices depend on the requested service. A quote is required; no flat rate is published."
PROPOSAL = {
    "blocks": [
        {
            "heading": "Pricing",
            "text": "Prices depend on the requested service. A quote is required; no flat rate is published.",
            "tags": ["pricing"],
        }
    ]
}


def test_heading_sections_are_not_packed_into_one_window() -> None:
    skip = "## Skip tracing\n\n" + ("nationwide addresses scored phones. " * 80)
    vpoe = "## VPOE\n\n" + ("payroll source employment dates. " * 80)
    text = f"{skip}\n\n{vpoe}"
    windows = page_windows(text, limit=4000)
    assert "".join(windows) == text
    assert len(windows) >= 2
    assert any("Skip tracing" in window and "VPOE" not in window for window in windows)
    assert any("VPOE" in window and "Skip tracing" not in window for window in windows)


def test_long_structured_block_fits_embed_size_without_dropping_facts() -> None:
    facts = [
        f"Fact {index:02d} is documented for skip tracing nationwide." for index in range(1, 31)
    ]
    text = " ".join(facts)
    unit = EvidenceUnit(
        kind="section",
        heading="Skip tracing",
        canonical_question=None,
        answer_verbatim=text,
        body_for_search=f"Skip tracing\n{text}",
        display_locator="https://example.com",
        aliases=("skip tracing",),
        structured_text=text,
    )
    chunks = pack_chunks(unit, target=900, overlap=150)
    assert all(len(chunk.body) <= 900 for chunk in chunks)
    blob = " ".join(chunk.answer_verbatim for chunk in chunks)
    for fact in facts:
        assert fact in blob
    assert all("Skip tracing" in chunk.body for chunk in chunks)


def test_information_block_keeps_a_full_section() -> None:
    text = "Skip tracing covers nationwide addresses, scored phones, and right-party contact. " * 12
    payload = PageBlocks.model_validate(
        {"blocks": [{"heading": "Skip tracing", "text": text, "tags": ["skip tracing"]}]}
    )
    assert payload.blocks[0].text == text


def test_source_passage_is_the_citable_answer() -> None:
    units = evidence_from_blocks(PageBlocks.model_validate(PROPOSAL), SOURCE, "https://example.com")
    chunk = pack_chunks(units[0])[0]
    assert chunk.answer_verbatim == (
        "Prices depend on the requested service. A quote is required; no flat rate is published."
    )
    assert "Prices depend on the requested service." in chunk.body
    assert units[0].enabled is True


def test_invented_number_disables_only_that_block() -> None:
    payload = PageBlocks.model_validate(
        {
            "blocks": [
                PROPOSAL["blocks"][0],
                {
                    "heading": "Fee",
                    "text": "The fee is $49.",
                    "tags": [],
                },
            ]
        }
    )
    units = evidence_from_blocks(payload, SOURCE, "https://example.com")
    by_heading = {unit.heading: unit for unit in units}
    assert by_heading["Pricing"].enabled is True
    assert by_heading["Fee"].enabled is False
    assert by_heading["Fee"].review_note == "unsupported_numeric_literal"


def test_rephrased_numeric_formatting_is_not_verbatim_source_evidence() -> None:
    payload = PageBlocks.model_validate(
        {
            "blocks": [
                {
                    "heading": "Throughput",
                    "text": "Steps 1, 2 and 3 process 1000 records at 1.5 each.",
                    "tags": [],
                }
            ]
        }
    )
    units = evidence_from_blocks(
        payload, "Steps 01, 02 and 03 process 1,000 records at 1.50 each.", ""
    )
    assert units[0].enabled is False
    assert units[0].review_note == "unsupported_source_text"
    assert units[0].answer_verbatim == "Steps 1, 2 and 3 process 1000 records at 1.5 each."


async def test_text_structuring_does_not_send_a_crawl_url(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-key")
    client = HaikuPageStructurer()
    captured = {}

    async def _call(_client, system, name, schema, data, usage):
        captured["name"] = name
        captured["data"] = data
        captured["system"] = system
        return PROPOSAL

    client._call = _call
    structured = await client.structure_text("Collections policy", SOURCE)
    assert captured["name"] == "structure_text"
    assert captured["data"]["source_kind"] == "text"
    assert "url" not in captured["data"]
    assert structured.units[0].enabled is True


async def test_page_pipeline_embeds_clean_text_from_crawl_markdown(
    migrated_db, monkeypatch
) -> None:
    from sqlalchemy import select

    from app.db import session_maker
    from app.models.kb_chunk import KbChunk
    from app.models.kb_page import KbPage
    from app.models.kb_snapshot import KbSnapshot
    from app.services.kb_embedder import FakeEmbedder
    from app.services.kb_fetcher import FetchResult, _digest
    from app.services.kb_ingest import ingest_source
    from app.services.kb_page_structure import StructuredPage
    from tests.test_kb_ingest_pipeline import FAQ_URL, _queued_source, fake_fetch

    crawl_text = ("navigation " * 500) + "\n\n" + SOURCE

    class PageClient:
        model = "test-page-structurer"
        received = None

        async def structure_page(self, url, title, text, metadata=None):
            self.received = {"url": url, "title": title, "text": text, "metadata": metadata}
            return StructuredPage(
                evidence_from_blocks(PageBlocks.model_validate(PROPOSAL), text, url),
            )

        async def structure_text(self, title, body):
            raise AssertionError("website ingest must not use the text structurer")

    async def fetch_page(url, _hosts, **_kwargs):
        html = "<article><h2>Unrelated card</h2><p>Unrelated text.</p></article>"
        return FetchResult(url, 200, html, crawl_text, _digest(html), title="Source")

    def unexpected_html_parser(*_args, **_kwargs):
        raise AssertionError("page structuring must not depend on website section parsers")

    monkeypatch.setattr("app.services.kb_pipeline.fetch_page", fetch_page)
    monkeypatch.setattr("app.services.kb_pipeline.extract_html", unexpected_html_parser)
    client = PageClient()
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        await ingest_source(
            session, source.id, embedder=FakeEmbedder(), fetch=fake_fetch, llm_client=client
        )
        assert client.received["text"] == crawl_text
        assert client.received["url"] == FAQ_URL
        assert source.status == "ready"
        page = await session.scalar(select(KbPage).where(KbPage.source_id == source.id))
        chunk = await session.scalar(
            select(KbChunk)
            .join(KbSnapshot, KbChunk.snapshot_id == KbSnapshot.id)
            .where(KbSnapshot.source_id == source.id, KbSnapshot.state == "live")
        )
        assert chunk.answer_verbatim == PROPOSAL["blocks"][0]["text"]
        assert "Prices depend on the requested service." in chunk.body
        assert page.content_text == chunk.body
        assert page.markdown == crawl_text


async def test_one_invented_block_does_not_discard_the_page(migrated_db, monkeypatch) -> None:
    from sqlalchemy import select

    from app.db import session_maker
    from app.models.kb_chunk import KbChunk
    from app.models.kb_snapshot import KbSnapshot
    from app.services.kb_embedder import FakeEmbedder
    from app.services.kb_fetcher import FetchResult, _digest
    from app.services.kb_ingest import ingest_source
    from app.services.kb_page_structure import StructuredPage
    from tests.test_kb_ingest_pipeline import FAQ_URL, _queued_source, fake_fetch

    crawl_text = (
        "Skip tracing covers nationwide addresses.\n\n"
        "A quote is required; no flat rate is published."
    )
    payload = {
        "blocks": [
            {
                "heading": "Skip tracing",
                "text": "Skip tracing covers nationwide addresses.",
                "tags": ["skip tracing"],
            },
            {
                "heading": "Fee",
                "text": "The published fee is $49.",
                "tags": [],
            },
        ]
    }

    class PageClient:
        model = "test-page-structurer"

        async def structure_page(self, url, title, text, metadata=None):
            del title, metadata
            return StructuredPage(
                evidence_from_blocks(PageBlocks.model_validate(payload), text, url),
            )

    async def fetch_page(url, _hosts, **_kwargs):
        return FetchResult(url, 200, "<p>ok</p>", crawl_text, _digest("<p>ok</p>"), title="Source")

    monkeypatch.setattr("app.services.kb_pipeline.fetch_page", fetch_page)
    async with session_maker()() as session:
        source = await _queued_source(session, [FAQ_URL])
        await ingest_source(
            session, source.id, embedder=FakeEmbedder(), fetch=fake_fetch, llm_client=PageClient()
        )
        assert source.status == "ready"
        chunks = list(
            (
                await session.scalars(
                    select(KbChunk)
                    .join(KbSnapshot, KbChunk.snapshot_id == KbSnapshot.id)
                    .where(KbSnapshot.source_id == source.id, KbSnapshot.state == "live")
                    .order_by(KbChunk.ordinal)
                )
            ).all()
        )
        enabled = [chunk for chunk in chunks if chunk.enabled]
        disabled = [chunk for chunk in chunks if not chunk.enabled]
        assert [chunk.answer_verbatim for chunk in enabled] == [
            "Skip tracing covers nationwide addresses."
        ]
        assert [chunk.answer_verbatim for chunk in disabled] == ["The published fee is $49."]
        assert disabled[0].review_note == "unsupported_numeric_literal"


def _section(heading: str, text: str) -> EvidenceUnit:
    return EvidenceUnit(
        kind="section",
        heading=heading,
        canonical_question=None,
        answer_verbatim=text,
        body_for_search=f"{heading}\n{text}",
        display_locator="https://sample-data.example.com/samplemail",
    )


def test_oversized_heading_and_tags_still_become_a_block() -> None:
    heading = "Gramm-Leach-Bliley Act (GLBA) and Driver's Privacy Protection Act (DPPA) Compliance"
    source = "Terms require GLBA and DPPA compliance for permitted uses."
    payload = page_blocks_from_proposal(
        {
            "blocks": [
                {
                    "heading": heading,
                    "text": source,
                    "tags": ["GLBA", "DPPA", "FCRA", "KYC/AML", "compliance"],
                }
            ]
        }
    )
    block = payload.blocks[0]
    assert block.heading == (
        "Gramm-Leach-Bliley Act (GLBA) and Driver's Privacy Protection Act (DPPA) Complia"
    )
    assert block.tags == ["GLBA", "DPPA", "FCRA", "KYC/AML", "compliance"]
    units = evidence_from_blocks(payload, source, "https://sample-data.example.com/terms")
    assert [unit.heading for unit in units] == [block.heading]
    assert units[0].aliases == ("GLBA", "DPPA", "compliance")
    assert units[0].enabled is True


def test_restated_blocks_on_one_page_keep_the_fuller_copy() -> None:
    short = "Every address is checked against proprietary data before entering the mailstream."
    full = (
        "Every address is checked against proprietary data before entering the mailstream. "
        "This prevents undeliverable mail from wasting print and postage."
    )
    unique = "SampleMail Plus appends missing and outdated addresses beyond standard NCOA."
    units = unique_units(
        [
            _section("Address Verification Service", short),
            _section("Address Verification with Proprietary Data", full),
            _section("SampleMail Plus", unique),
        ]
    )
    assert [unit.heading for unit in units] == [
        "Address Verification with Proprietary Data",
        "SampleMail Plus",
    ]
    assert [unit.answer_verbatim for unit in units] == [full, unique]


def test_whitespace_only_contact_repeat_is_dropped() -> None:
    first = "Phone: 202-555-0101. Email: inquiries@sample-data.example.com"
    second = "Phone: 202-555-0101\nEmail: inquiries@sample-data.example.com"
    units = unique_units(
        [
            _section("Contact Information", first),
            _section("Sample Data Services Contact Information", second),
        ]
    )
    assert [unit.heading for unit in units] == ["Contact Information"]
    assert units[0].answer_verbatim == first


def test_distinct_product_blocks_on_one_page_are_kept() -> None:
    skip = "Skip tracing covers nationwide addresses, scored phones, and right-party contact."
    vpoe = "VPOE is a verified employment record sourced for permissible-use collections."
    units = unique_units(
        [
            _section("Skip Tracing Service", skip),
            _section("VPOE", vpoe),
        ]
    )
    assert [unit.answer_verbatim for unit in units] == [skip, vpoe]
