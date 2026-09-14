import uuid

import pytest

from app.services.grounded_response import (
    EvidenceUnit,
    GroundedResponseEngine,
    ModelDraft,
    ResponseOutcome,
    TurnContext,
)

TIMING = EvidenceUnit(
    id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    canonical_question="How quickly are results available?",
    aliases=(),
    topic_label="Turnaround",
    answer_verbatim="Most negative results are reported within 24-48 hours.",
    source_title="Turnaround",
    source_url="https://example.test/a",
)


@pytest.mark.asyncio
async def test_model_authored_question_without_citations_falls_back_extractively() -> None:
    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(
            body="Are you setting up pre-employment screens, a random program, or DOT testing?",
            citations=[],
        )

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="How fast are results?", evidence=[TIMING])
    )

    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
    assert decision.reason_code == "extractive_fallback"
    assert decision.body == TIMING.answer_verbatim


@pytest.mark.asyncio
async def test_factual_claim_without_citations_falls_back_extractively() -> None:
    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=TIMING.answer_verbatim, citations=[])

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="How fast are results?", evidence=[TIMING])
    )

    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
    assert decision.reason_code == "extractive_fallback"
    assert decision.body == TIMING.answer_verbatim
