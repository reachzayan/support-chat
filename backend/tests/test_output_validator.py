import uuid

from app.services.output_validator import evaluate

CLARIFY = "Are you setting up pre-employment screens, a random program, or DOT testing?"
TIMING_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TIMING_BODY = "Most negative results are reported within 24-48 hours."


def test_uncited_factual_text_ending_in_a_question_is_rejected() -> None:
    outcome = evaluate(
        "We are federally registered with DOT. Would you like our number?",
        allowed_ids=[TIMING_ID],
        cited=[],
    )
    assert outcome.accepted is False
    assert outcome.reason == "no_citation"


def test_factual_claim_without_citations_is_rejected() -> None:
    outcome = evaluate(TIMING_BODY, allowed_ids=[TIMING_ID], cited=[])
    assert outcome.accepted is False
    assert outcome.reason == "no_citation"
