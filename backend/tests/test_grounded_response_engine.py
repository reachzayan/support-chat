# ruff: noqa: RUF001

import uuid

import pytest

from app.services.grounded_response import (
    Citation,
    EvidenceUnit,
    GroundedResponseEngine,
    ModelDraft,
    ProviderStatus,
    ResponseOutcome,
    TurnContext,
)

DOT_SERVICES = EvidenceUnit(
    id=uuid.UUID("10000000-0000-4000-8000-000000000001"),
    canonical_question="What DOT services do you provide?",
    aliases=("DOT compliance",),
    topic_label="DOT testing services",
    answer_verbatim="We support DOT drug and alcohol testing, random pool management, MIS reporting, and DOT physicals.",
    source_title="DOT services",
    source_url="https://example.test/dot",
)
USDOT_CREDENTIAL = EvidenceUnit(
    id=uuid.UUID("10000000-0000-4000-8000-000000000002"),
    canonical_question="What is your USDOT number?",
    aliases=("DOT registration",),
    topic_label="USDOT registration",
    answer_verbatim="A specialist can verify company registration details.",
    source_title="Company registration",
    source_url="https://example.test/registration",
    risk_class="credential",
    answer_mode="human_only",
)

SCREENING_SERVICES = EvidenceUnit(
    id=uuid.UUID("10000000-0000-4000-8000-000000000003"),
    canonical_question="Which screening services do you provide?",
    aliases=(),
    topic_label="Screening services",
    answer_verbatim="We provide drug and alcohol testing, sample services, and random pool management.",
    source_title="Screening services",
    source_url="https://example.test/screening",
)
OCCUPATIONAL_HEALTH = EvidenceUnit(
    id=uuid.UUID("10000000-0000-4000-8000-000000000004"),
    canonical_question="Which occupational health services do you provide?",
    aliases=(),
    topic_label="Occupational health services",
    answer_verbatim="We provide physical exams, TB tests, and vaccinations.",
    source_title="Occupational health services",
    source_url="https://example.test/occupational-health",
)


@pytest.mark.asyncio
async def test_exact_approved_answer_is_verbatim_and_never_calls_the_model() -> None:
    calls = 0

    async def complete(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return "ignored"

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(visitor_text="What DOT services do you provide?", evidence=[DOT_SERVICES])
    )

    assert decision.outcome is ResponseOutcome.EXACT_ANSWER
    assert decision.body == DOT_SERVICES.answer_verbatim
    assert [citation.chunk_id for citation in decision.citations] == [DOT_SERVICES.id]
    assert calls == 0


@pytest.mark.asyncio
async def test_supported_services_overview_synthesizes_instead_of_clarifying() -> None:
    body = f"{SCREENING_SERVICES.answer_verbatim} {OCCUPATIONAL_HEALTH.answer_verbatim}"
    calls = 0

    async def complete(_turn: TurnContext, units: list[EvidenceUnit]) -> ModelDraft:
        nonlocal calls
        calls += 1
        assert {unit.id for unit in units} == {SCREENING_SERVICES.id, OCCUPATIONAL_HEALTH.id}
        first_end = len(SCREENING_SERVICES.answer_verbatim)
        return ModelDraft(
            body=body,
            citations=[
                Citation(
                    chunk_id=SCREENING_SERVICES.id,
                    snapshot_id=None,
                    response_start=0,
                    response_end=first_end,
                    source_start=0,
                    source_end=first_end,
                    cited_text=SCREENING_SERVICES.answer_verbatim,
                    source_title=SCREENING_SERVICES.source_title,
                    source_url=SCREENING_SERVICES.source_url,
                ),
                Citation(
                    chunk_id=OCCUPATIONAL_HEALTH.id,
                    snapshot_id=None,
                    response_start=first_end + 1,
                    response_end=len(body),
                    source_start=0,
                    source_end=len(OCCUPATIONAL_HEALTH.answer_verbatim),
                    cited_text=OCCUPATIONAL_HEALTH.answer_verbatim,
                    source_title=OCCUPATIONAL_HEALTH.source_title,
                    source_url=OCCUPATIONAL_HEALTH.source_url,
                ),
            ],
        )

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(
            visitor_text="Can you tell me what services you offer?",
            evidence=[SCREENING_SERVICES, OCCUPATIONAL_HEALTH],
        )
    )

    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
    assert decision.body == body
    assert [citation.chunk_id for citation in decision.citations] == [
        SCREENING_SERVICES.id,
        OCCUPATIONAL_HEALTH.id,
    ]
    assert calls == 1


@pytest.mark.asyncio
async def test_dot_registration_question_asks_a_server_owned_clarification() -> None:
    decision = await GroundedResponseEngine().respond(
        TurnContext(
            visitor_text="Are you registered with DOT?",
            evidence=[DOT_SERVICES, USDOT_CREDENTIAL],
        )
    )

    assert decision.outcome is ResponseOutcome.CLARIFICATION
    assert decision.body == "Are you asking about DOT testing services or USDOT registration?"
    assert decision.citations == []


@pytest.mark.asyncio
async def test_unverified_usdot_number_is_a_knowledge_gap_not_a_claim() -> None:
    decision = await GroundedResponseEngine().respond(
        TurnContext(visitor_text="What is your USDOT number?", evidence=[DOT_SERVICES])
    )

    assert decision.outcome is ResponseOutcome.KNOWLEDGE_GAP
    assert "verified information" in decision.body
    assert "DOT testing services" in decision.body
    assert decision.citations == []


@pytest.mark.asyncio
async def test_combined_services_and_registration_question_is_partial() -> None:
    decision = await GroundedResponseEngine().respond(
        TurnContext(
            visitor_text="Do you provide DOT services and are you registered with DOT?",
            evidence=[DOT_SERVICES],
        )
    )

    assert decision.outcome is ResponseOutcome.PARTIAL_ANSWER
    assert decision.body.startswith(DOT_SERVICES.answer_verbatim)
    assert "can’t verify whether you are registered with DOT" in decision.body
    assert [citation.chunk_id for citation in decision.citations] == [DOT_SERVICES.id]


@pytest.mark.asyncio
async def test_frustration_is_deterministic_recovery_copy() -> None:
    decision = await GroundedResponseEngine().respond(
        TurnContext(visitor_text="It is a simple question, are you dumb?", evidence=[DOT_SERVICES])
    )

    assert decision.outcome is ResponseOutcome.BOUNDARY
    assert decision.reason_code == "frustration"
    assert (
        decision.body
        == "I’m sorry—that wasn’t helpful. Tell me what you need confirmed, or I can connect you with a specialist."
    )


@pytest.mark.asyncio
async def test_provider_failure_returns_a_grounded_extractive_answer() -> None:
    async def fail(_turn: TurnContext, _units: list[EvidenceUnit]) -> None:
        return None

    decision = await GroundedResponseEngine(complete=fail).respond(
        TurnContext(visitor_text="What services do you provide?", evidence=[SCREENING_SERVICES])
    )

    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
    assert decision.reason_code == "extractive_fallback"
    assert decision.body == SCREENING_SERVICES.answer_verbatim
    assert decision.provider_status is ProviderStatus.TECH_FAIL
    assert [citation.chunk_id for citation in decision.citations] == [SCREENING_SERVICES.id]


@pytest.mark.asyncio
async def test_invalid_model_draft_returns_only_verbatim_evidence() -> None:
    invented = "We also provide an unsupported premium concierge service."

    async def complete(_turn: TurnContext, _units: list[EvidenceUnit]) -> ModelDraft:
        return ModelDraft(body=invented, citations=[])

    decision = await GroundedResponseEngine(complete=complete).respond(
        TurnContext(
            visitor_text="What services do you provide?",
            evidence=[SCREENING_SERVICES, OCCUPATIONAL_HEALTH],
        )
    )

    assert decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
    assert decision.reason_code == "extractive_fallback"
    assert invented not in decision.body
    assert decision.body == (
        f"{SCREENING_SERVICES.answer_verbatim}\n\n{OCCUPATIONAL_HEALTH.answer_verbatim}"
    )
    assert [citation.cited_text for citation in decision.citations] == [
        SCREENING_SERVICES.answer_verbatim,
        OCCUPATIONAL_HEALTH.answer_verbatim,
    ]
