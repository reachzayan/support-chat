import uuid

import pytest

from app.chat.outcome_copy import INSUFFICIENT_HUMAN, UNCITED_ADVISORY_SUFFIX
from app.services.grounded_response import (
    EvidenceUnit,
    GroundedResponseEngine,
    ModelDraft,
    ProviderStatus,
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
async def test_model_authored_clarification_without_citations_is_accepted() -> None:
    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(
            body="Are you setting up pre-employment screens, a random program, or occupational health?",
            citations=[],
        )

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="How fast are results?", evidence=[TIMING])
    )

    assert decision.outcome is ResponseOutcome.CLARIFICATION
    assert decision.body.endswith("?")
    assert decision.offer_handoff is False


@pytest.mark.asyncio
async def test_source_copy_without_citations_still_rejects() -> None:
    """Exact FAQ paste stays a hard reject even when Claude emits no citations."""

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=TIMING.answer_verbatim, citations=[])

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="How fast are results?", evidence=[TIMING])
    )

    assert decision.outcome is ResponseOutcome.KNOWLEDGE_GAP
    assert decision.reason_code == "grounding_reject"
    assert decision.body == INSUFFICIENT_HUMAN
    assert decision.offer_handoff is True
    assert decision.provider_status is ProviderStatus.OK


@pytest.mark.asyncio
async def test_paraphrased_uncited_claim_gets_advisory_suffix() -> None:
    body = "Negative panels are usually available within a business day or two."

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=body, citations=[], request_id="req_advisory")

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="How fast are results?", evidence=[TIMING])
    )

    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
    assert decision.reason_code == "uncited_advisory"
    assert decision.body.startswith(body)
    assert decision.body.endswith(UNCITED_ADVISORY_SUFFIX)
    assert decision.offer_handoff is True
    assert decision.provider_status is ProviderStatus.OK
