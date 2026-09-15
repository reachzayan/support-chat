import uuid

import pytest
from structlog.testing import capture_logs

from app.chat.outcome_copy import INSUFFICIENT_HUMAN, TECH_FAIL_HUMAN, UNCITED_ADVISORY_SUFFIX
from app.services.grounded_response import (
    Citation,
    EvidenceUnit,
    GroundedResponseEngine,
    ModelDraft,
    ProviderStatus,
    ResponseOutcome,
    TurnContext,
)

DOT_EVIDENCE = EvidenceUnit(
    id=uuid.UUID("10000000-0000-4000-8000-000000000001"),
    canonical_question="Do you provide DOT drug and alcohol testing?",
    aliases=(),
    topic_label="DOT testing",
    answer_verbatim=(
        "We support DOT drug and alcohol testing, random pool management, and DOT physicals."
    ),
    source_title="DOT services",
    source_url="https://example.test/dot",
    snapshot_id=uuid.UUID("20000000-0000-4000-8000-000000000001"),
)

TIMING_EVIDENCE = EvidenceUnit(
    id=uuid.UUID("10000000-0000-4000-8000-000000000002"),
    canonical_question="How quickly are results available?",
    aliases=(),
    topic_label="Turnaround",
    answer_verbatim="Results are reported in 24 to 48 hours.",
    source_title="Turnaround",
    source_url="https://example.test/timing",
    snapshot_id=uuid.UUID("20000000-0000-4000-8000-000000000002"),
)


def _citation(unit: EvidenceUnit, body: str) -> Citation:
    return Citation(
        chunk_id=unit.id,
        snapshot_id=unit.snapshot_id,
        response_start=0,
        response_end=len(body),
        source_start=0,
        source_end=len(unit.answer_verbatim),
        cited_text=unit.answer_verbatim,
        source_title=unit.source_title,
        source_url=unit.source_url,
    )


@pytest.mark.asyncio
async def test_paraphrased_factual_answer_is_accepted() -> None:
    body = "Yes. We handle DOT drug and alcohol testing."

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=body, citations=[_citation(DOT_EVIDENCE, body)])

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="Do you provide drug screening?", evidence=[DOT_EVIDENCE])
    )

    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
    assert decision.body == body
    assert decision.citations[0].chunk_id == DOT_EVIDENCE.id
    assert decision.provider_status is ProviderStatus.OK


@pytest.mark.asyncio
async def test_source_copy_is_rejected_as_grounding_reject() -> None:
    body = DOT_EVIDENCE.answer_verbatim

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=body, citations=[_citation(DOT_EVIDENCE, body)])

    with capture_logs() as events:
        decision = await GroundedResponseEngine(complete=complete).respond(
            TurnContext(visitor_text="Do you provide drug screening?", evidence=[DOT_EVIDENCE])
        )

    assert decision.reason_code == "grounding_reject"
    assert decision.body == INSUFFICIENT_HUMAN
    assert decision.offer_handoff is True
    assert decision.provider_status is ProviderStatus.OK
    assert decision.citations == []
    assert any(
        event.get("event") == "grounded_draft_reject" and event.get("reason") == "source_copy"
        for event in events
    )


@pytest.mark.asyncio
async def test_clarifying_question_still_bypasses_citation_requirement() -> None:
    body = "Are you asking about small-fleet enrollment?"

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=body, citations=[], request_id="req_clarify")

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="tell me more", evidence=[DOT_EVIDENCE])
    )

    assert decision.outcome is ResponseOutcome.CLARIFICATION
    assert decision.body == body
    assert not decision.body.endswith(UNCITED_ADVISORY_SUFFIX)
    assert UNCITED_ADVISORY_SUFFIX not in decision.body
    assert decision.offer_handoff is False
    assert decision.reason_code is None
    assert decision.provider_status is ProviderStatus.OK


@pytest.mark.asyncio
async def test_unsupported_numeric_still_rejects_to_insufficient() -> None:
    body = "Results come back in 12 hours."

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=body, citations=[_citation(TIMING_EVIDENCE, body)])

    with capture_logs() as events:
        decision = await GroundedResponseEngine(complete=complete).respond(
            TurnContext(visitor_text="How fast are results?", evidence=[TIMING_EVIDENCE])
        )

    assert decision.reason_code == "grounding_reject"
    assert decision.body == INSUFFICIENT_HUMAN
    assert decision.offer_handoff is True
    assert decision.provider_status is ProviderStatus.OK
    assert any(
        event.get("event") == "grounded_draft_reject"
        and event.get("reason") == "unsupported_numeric"
        for event in events
    )


@pytest.mark.asyncio
async def test_unsupported_regulated_still_rejects_to_insufficient() -> None:
    body = "We follow HIPAA rules for every panel."

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=body, citations=[_citation(DOT_EVIDENCE, body)])

    with capture_logs() as events:
        decision = await GroundedResponseEngine(complete=complete).respond(
            TurnContext(visitor_text="Do you handle privacy rules?", evidence=[DOT_EVIDENCE])
        )

    assert decision.reason_code == "grounding_reject"
    assert decision.body == INSUFFICIENT_HUMAN
    assert decision.offer_handoff is True
    assert decision.provider_status is ProviderStatus.OK
    assert any(
        event.get("event") == "grounded_draft_reject"
        and event.get("reason") == "unsupported_regulated"
        for event in events
    )


@pytest.mark.asyncio
async def test_no_citation_returns_advisory_not_reject() -> None:
    body = (
        "We provide DOT drug testing for small employers. "
        "A specialist can confirm details for your specific case."
    )

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=body, citations=[], request_id="req_test")

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="Do you provide drug screening?", evidence=[DOT_EVIDENCE])
    )

    assert decision.body.startswith("We provide DOT drug testing for small employers.")
    assert decision.body.endswith(UNCITED_ADVISORY_SUFFIX)
    assert "\n\n" in decision.body
    assert decision.offer_handoff is True
    assert decision.reason_code == "uncited_advisory"
    assert decision.provider_status is ProviderStatus.OK
    assert decision.citations == []
    assert decision.request_id == "req_test"
    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER


@pytest.mark.asyncio
async def test_provider_exception_still_routes_to_tech_fail() -> None:
    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        raise RuntimeError("boom")

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="Do you provide drug screening?", evidence=[DOT_EVIDENCE])
    )

    assert decision.body == TECH_FAIL_HUMAN
    assert decision.reason_code == "tech_fail"
    assert decision.provider_status is ProviderStatus.TECH_FAIL


@pytest.mark.asyncio
async def test_empty_draft_still_routes_to_tech_fail() -> None:
    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body="", citations=[], request_id="req_empty")

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="Do you provide drug screening?", evidence=[DOT_EVIDENCE])
    )

    assert decision.body == TECH_FAIL_HUMAN
    assert decision.reason_code == "tech_fail"
    assert decision.provider_status is ProviderStatus.TECH_FAIL


@pytest.mark.asyncio
async def test_stale_source_helper_still_routes_to_tech_fail() -> None:
    from app.services.grounded_response import _safe_technical_failure

    decision = _safe_technical_failure(reason="stale_source")

    assert decision.body == TECH_FAIL_HUMAN
    assert decision.reason_code == "tech_fail"
    assert decision.provider_status is ProviderStatus.TECH_FAIL


@pytest.mark.asyncio
async def test_no_evidence_skips_provider_and_offers_handoff() -> None:
    calls = {"count": 0}

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        calls["count"] += 1
        return ModelDraft(body="should not run", citations=[])

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="Do you provide drug screening?", evidence=[])
    )

    assert decision.outcome is ResponseOutcome.KNOWLEDGE_GAP
    assert decision.offer_handoff is True
    assert decision.body == INSUFFICIENT_HUMAN
    assert calls["count"] == 0
