import uuid

import pytest
from structlog.testing import capture_logs

from app.chat.outcome_copy import TECH_FAIL_HUMAN, TRANSFER_OFFER
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

CLARIFY_SCOPE_LINE = "What would you like to know about screening or compliance?"
PRODUCTS_CLARIFY = "What would you like to know about our products or services?"
GROUNDING_REJECT = "I couldn't verify an accurate answer to that question. A specialist can help."
PRODUCTS_KEEP_HELPING = (
    "I can help with questions about our products and services. What do you need?"
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


async def test_forged_source_text_with_valid_chunk_id_is_rejected() -> None:
    from dataclasses import replace

    body = "Results are guaranteed in 12 hours."

    async def complete(_turn, _units):
        return ModelDraft(body, [replace(_citation(TIMING_EVIDENCE, body), cited_text=body)])

    decision = await GroundedResponseEngine(complete).respond(
        TurnContext(visitor_text="How long?", evidence=[TIMING_EVIDENCE])
    )
    assert decision.body == GROUNDING_REJECT
    assert decision.reason_code == "grounding_reject"


async def test_connective_words_between_cited_service_names_are_allowed() -> None:
    from dataclasses import replace

    body = "These include DOT physicals and random pool management."
    citations = [
        replace(
            _citation(DOT_EVIDENCE, body),
            response_start=body.index(phrase),
            response_end=body.index(phrase) + len(phrase),
        )
        for phrase in ("DOT physicals", "random pool management.")
    ]

    async def complete(_turn, _units):
        return ModelDraft(body, citations)

    decision = await GroundedResponseEngine(complete).respond(
        TurnContext(visitor_text="What services?", evidence=[DOT_EVIDENCE])
    )
    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
    assert decision.body == body


async def test_one_valid_citation_does_not_authorize_an_uncited_business_claim() -> None:
    from dataclasses import replace

    body = "We provide DOT testing. All customers receive free annual audits."

    async def complete(_turn, _units):
        return ModelDraft(body, [replace(_citation(DOT_EVIDENCE, body), response_end=23)])

    decision = await GroundedResponseEngine(complete).respond(
        TurnContext(visitor_text="What is included?", evidence=[DOT_EVIDENCE])
    )
    assert decision.body == GROUNDING_REJECT
    assert "free annual audits" not in decision.body
    assert decision.reason_code == "grounding_reject"
    assert decision.outcome is ResponseOutcome.KNOWLEDGE_GAP


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
async def test_single_cited_source_answer_is_accepted() -> None:
    body = DOT_EVIDENCE.answer_verbatim

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=body, citations=[_citation(DOT_EVIDENCE, body)])

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="Do you provide drug screening?", evidence=[DOT_EVIDENCE])
    )

    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
    assert decision.reason_code is None
    assert decision.body == body
    assert decision.offer_handoff is False
    assert decision.provider_status is ProviderStatus.OK
    assert decision.citations[0].chunk_id == DOT_EVIDENCE.id


@pytest.mark.asyncio
async def test_stitched_source_dump_is_still_rejected() -> None:
    body = f"{DOT_EVIDENCE.answer_verbatim}\n\n{TIMING_EVIDENCE.answer_verbatim}"
    second_start = len(DOT_EVIDENCE.answer_verbatim) + 2

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(
            body=body,
            citations=[
                _citation(DOT_EVIDENCE, body),
                Citation(
                    chunk_id=TIMING_EVIDENCE.id,
                    snapshot_id=TIMING_EVIDENCE.snapshot_id,
                    response_start=second_start,
                    response_end=len(body),
                    source_start=0,
                    source_end=len(TIMING_EVIDENCE.answer_verbatim),
                    cited_text=TIMING_EVIDENCE.answer_verbatim,
                    source_title=TIMING_EVIDENCE.source_title,
                    source_url=TIMING_EVIDENCE.source_url,
                ),
            ],
        )

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(
            visitor_text="Tell me everything about DOT testing and turnaround.",
            evidence=[DOT_EVIDENCE, TIMING_EVIDENCE],
        )
    )

    assert decision.outcome is ResponseOutcome.KNOWLEDGE_GAP
    assert decision.reason_code == "grounding_reject"
    assert decision.body == GROUNDING_REJECT


@pytest.mark.asyncio
async def test_clarifying_question_still_bypasses_citation_requirement() -> None:
    body = "Are you asking about small-fleet enrollment?"

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=body, citations=[], request_id="req_clarify")

    assistant_text = "We support several DOT testing services."
    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(
            visitor_text="tell me more",
            prior_messages=({"role": "assistant", "content": assistant_text},),
            evidence=[DOT_EVIDENCE],
        )
    )

    assert decision.outcome is ResponseOutcome.CLARIFICATION
    assert decision.body == body
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
    assert decision.body == GROUNDING_REJECT
    assert decision.offer_handoff is False
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
            TurnContext(visitor_text="Do you handle DOT privacy rules?", evidence=[DOT_EVIDENCE])
        )

    assert decision.reason_code == "grounding_reject"
    assert decision.body == GROUNDING_REJECT
    assert decision.offer_handoff is False
    assert decision.provider_status is ProviderStatus.OK
    assert any(
        event.get("event") == "grounded_draft_reject"
        and event.get("reason") == "unsupported_regulated"
        for event in events
    )


@pytest.mark.asyncio
async def test_no_citation_rejects_factual_draft() -> None:
    body = (
        "We provide DOT drug testing for small employers. "
        "A specialist can confirm details for your specific case."
    )

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=body, citations=[], request_id="req_test")

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="Do you provide drug screening?", evidence=[DOT_EVIDENCE])
    )

    assert decision.body == GROUNDING_REJECT
    assert decision.offer_handoff is False
    assert decision.reason_code == "grounding_reject"
    assert decision.provider_status is ProviderStatus.OK
    assert decision.citations == []
    assert decision.request_id == "req_test"
    assert decision.outcome is ResponseOutcome.KNOWLEDGE_GAP


@pytest.mark.asyncio
async def test_second_grounding_reject_asks_before_transfer() -> None:
    body = "We provide DOT drug testing for small employers."

    async def complete(_turn, _units):
        return ModelDraft(body, citations=[])

    decision = await GroundedResponseEngine(complete).respond(
        TurnContext(
            visitor_text="What is included?",
            evidence=[DOT_EVIDENCE],
            prior_miss_count=1,
            prior_miss_reason="grounding_reject",
        )
    )
    assert decision.body == TRANSFER_OFFER
    assert decision.offer_handoff is True
    assert decision.reason_code == "repeated_miss"
    assert decision.outcome is ResponseOutcome.KNOWLEDGE_GAP


@pytest.mark.asyncio
async def test_samplesite_first_grounding_reject_reports_verification_failure() -> None:
    async def complete(_turn, _units):
        return ModelDraft(body="Results come back in 12 hours.", citations=[])

    decision = await GroundedResponseEngine(complete).respond(
        TurnContext(
            visitor_text="How fast?",
            evidence=[TIMING_EVIDENCE],
            site_name="SampleSite",
        )
    )
    assert decision.body == GROUNDING_REJECT
    assert decision.offer_handoff is False


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
async def test_grounding_reject_after_an_off_topic_miss_does_not_offer_transfer() -> None:
    body = "We provide DOT drug testing for small employers."

    async def complete(_turn, _units):
        return ModelDraft(body, citations=[])

    decision = await GroundedResponseEngine(complete).respond(
        TurnContext(
            visitor_text="Do you provide DOT testing?",
            evidence=[DOT_EVIDENCE],
            prior_miss_count=1,
            prior_miss_reason="no_evidence",
        )
    )
    assert decision.body == GROUNDING_REJECT
    assert decision.offer_handoff is False
    assert decision.reason_code == "grounding_reject"
    assert decision.outcome is ResponseOutcome.KNOWLEDGE_GAP


@pytest.mark.asyncio
async def test_page_followup_without_a_prior_answer_is_still_a_clarify() -> None:
    decision = await GroundedResponseEngine(complete=None).respond(
        TurnContext(visitor_text="Which page did that come from?", evidence=[])
    )
    assert decision.body == PRODUCTS_CLARIFY
    assert decision.reason_code == "no_evidence"


@pytest.mark.asyncio
async def test_model_scoped_redirect_is_an_off_topic_boundary() -> None:
    calls = {"count": 0}

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        calls["count"] += 1
        return ModelDraft(body=PRODUCTS_CLARIFY, citations=[])

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="Who is going to win the World Series?", evidence=[DOT_EVIDENCE])
    )
    assert decision.body == PRODUCTS_CLARIFY
    assert decision.reason_code == "off_topic"
    assert decision.offer_handoff is False
    assert decision.outcome is ResponseOutcome.BOUNDARY
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_repeated_model_scoped_redirect_does_not_hand_off() -> None:
    async def complete(_turn, _units):
        return ModelDraft(body=PRODUCTS_CLARIFY, citations=[])

    decision = await GroundedResponseEngine(complete).respond(
        TurnContext(
            visitor_text="Pick a horse at Churchill Downs.",
            evidence=[DOT_EVIDENCE],
            prior_miss_count=1,
            prior_miss_reason="no_evidence",
        )
    )
    assert decision.body == PRODUCTS_CLARIFY
    assert decision.offer_handoff is False
    assert decision.reason_code == "off_topic"


@pytest.mark.asyncio
async def test_grounding_reject_does_not_inherit_an_untyped_miss_count() -> None:
    async def complete(_turn, _units):
        return ModelDraft(body="We provide DOT drug testing for small employers.", citations=[])

    decision = await GroundedResponseEngine(complete).respond(
        TurnContext(
            visitor_text="How are skip-tracing phone numbers scored?",
            evidence=[DOT_EVIDENCE],
            prior_miss_count=2,
            prior_miss_reason=None,
        )
    )
    assert decision.body == GROUNDING_REJECT
    assert decision.offer_handoff is False
    assert decision.reason_code == "grounding_reject"


@pytest.mark.asyncio
async def test_first_no_evidence_miss_asks_neutral_clarification() -> None:
    calls = {"count": 0}

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        calls["count"] += 1
        return ModelDraft(body="should not run", citations=[])

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="Do you provide drug screening?", evidence=[])
    )

    assert decision.outcome is ResponseOutcome.CLARIFICATION
    assert decision.reason_code == "no_evidence"
    assert decision.offer_handoff is False
    assert decision.body == PRODUCTS_CLARIFY
    assert calls["count"] == 0


@pytest.mark.asyncio
async def test_samplesite_no_evidence_keeps_screening_clarification() -> None:
    decision = await GroundedResponseEngine(complete=None).respond(
        TurnContext(
            visitor_text="what's the weather in Dallas",
            evidence=[],
            site_name="SampleSite",
        )
    )
    assert decision.body == CLARIFY_SCOPE_LINE
    assert decision.reason_code == "no_evidence"


@pytest.mark.asyncio
async def test_courtesy_is_preserved_with_cited_sentence() -> None:
    from dataclasses import replace

    cited = "We support DOT drug and alcohol testing, random pool management, and DOT physicals."
    body = f"Happy to help. {cited}"
    start = body.index(cited)

    async def complete(_turn, _units):
        return ModelDraft(
            body,
            [replace(_citation(DOT_EVIDENCE, body), response_start=start, response_end=len(body))],
        )

    decision = await GroundedResponseEngine(complete).respond(
        TurnContext(visitor_text="What testing do you support?", evidence=[DOT_EVIDENCE])
    )
    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
    assert decision.body == body
    assert decision.reason_code is None
