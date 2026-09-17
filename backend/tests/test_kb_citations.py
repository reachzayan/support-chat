import uuid
from types import SimpleNamespace

from app.llm.bot_responder import BotResponder, output_is_safe

EASY_BODY = "Most negative results are reported within 24-48 hours."
TIMING_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TIMING_URL = "https://sample-site.example.com/turnaround"
EVIL_URL = "https://evil.example/pwn"


def _hit(chunk_id: uuid.UUID, url: str = TIMING_URL):
    return SimpleNamespace(
        id=chunk_id,
        title="Turnaround",
        heading="Turnaround",
        body=EASY_BODY,
        url=url,
    )


def _site():
    return SimpleNamespace(name="SampleSite")


async def test_generate_without_citations_is_rejected() -> None:
    async def complete(_prompt: str) -> str:
        return EASY_BODY

    answer = await BotResponder(complete=complete).generate(
        _site(), "how fast are results", [_hit(TIMING_ID)]
    )
    assert answer.accepted is False
    assert answer.source_chunk_ids == []
    assert answer.body == EASY_BODY


async def test_generate_keeps_cited_retrieved_chunk() -> None:
    async def complete(_prompt: str) -> str:
        return f"{EASY_BODY}\nSOURCES: {TIMING_ID}"

    answer = await BotResponder(complete=complete).generate(
        _site(), "how fast are results", [_hit(TIMING_ID)]
    )
    assert answer.accepted is True
    assert answer.source_chunk_ids == [TIMING_ID]
    assert answer.body == EASY_BODY


async def test_foreign_citation_url_is_discarded() -> None:
    async def complete(_prompt: str) -> str:
        return f"{EASY_BODY}\nSOURCES: {EVIL_URL}"

    answer = await BotResponder(complete=complete).generate(
        _site(), "how fast are results", [_hit(TIMING_ID)]
    )
    assert answer.accepted is False
    assert answer.source_chunk_ids == []


def test_output_is_safe_rejects_script() -> None:
    assert output_is_safe("<script>alert(1)</script>", [TIMING_ID], [TIMING_ID]) is False
    assert output_is_safe(EASY_BODY, [TIMING_ID], [TIMING_ID]) is True


def test_document_index_citation_maps_to_retrieved_chunk() -> None:
    from app.llm.bot_responder import join_sdk_completion

    hits = [_hit(TIMING_ID)]
    raw = join_sdk_completion(
        [
            SimpleNamespace(
                type="text",
                text=EASY_BODY,
                citations=[SimpleNamespace(document_index=0)],
            )
        ],
        hits,
    )
    assert raw == f"{EASY_BODY}\nSOURCES: {TIMING_ID}"


def test_native_citation_survives_response_whitespace_trimming() -> None:
    from app.llm.bot_responder import extract_native_citations

    body, citations = extract_native_citations(
        [
            SimpleNamespace(
                type="text",
                text=f"\n{EASY_BODY}\n",
                citations=[
                    SimpleNamespace(
                        document_index=0,
                        start_char_index=0,
                        end_char_index=len(EASY_BODY),
                        cited_text=EASY_BODY,
                    )
                ],
            )
        ],
        [_hit(TIMING_ID)],
    )
    assert body == "Most negative results are reported within 24-48 hours."
    assert len(citations) == 1
    assert citations[0].response_start == 0
    assert citations[0].response_end == len(body)
