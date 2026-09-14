import uuid

from app.services.full_context import EvidenceDoc, units_matching_query

TIMING_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TIMING_BODY = "Most negative results are reported within 24-48 hours."


def _unit() -> EvidenceDoc:
    return EvidenceDoc(
        id=TIMING_ID,
        snapshot_id=uuid.uuid4(),
        page_id=uuid.uuid4(),
        heading="How quickly are results available?",
        canonical_question="How quickly are results available?",
        answer_verbatim=TIMING_BODY,
        url="https://example.test/timing",
        title="Turnaround",
        display_locator=None,
        legal_sensitive=False,
        ordinal=0,
    )


def test_setup_question_still_sends_corpus_when_word_overlap_is_empty() -> None:
    units = [_unit()]
    matched = units_matching_query(units, "can you help us get set up for testing?")
    assert [item.id for item in matched] == [TIMING_ID]
