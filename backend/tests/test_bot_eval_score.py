from app.chat.outcome_copy import OFF_TOPIC_LINE, TRANSFER_OFFER, WAITING_LINE
from app.services.bot_eval import EvalCase, ObservedReply, score_case


def test_off_topic_passes_on_canned_line_and_stays_bot() -> None:
    case = EvalCase(
        id="off_topic.sad",
        family="routing.off_topic",
        turns=("I am sad",),
        expected_state="bot",
        expected_reason="off_topic",
        expected_copy=OFF_TOPIC_LINE,
    )
    observed = ObservedReply(
        state="bot",
        role="system",
        body=OFF_TOPIC_LINE,
        system_reason="off_topic",
    )
    verdict = score_case(case, observed)
    assert verdict.passed is True
    assert verdict.failures == ()


def test_off_topic_fails_when_conversation_is_queued() -> None:
    case = EvalCase(
        id="off_topic.sad",
        family="routing.off_topic",
        turns=("I am sad",),
        expected_state="bot",
        expected_reason="off_topic",
        expected_copy=OFF_TOPIC_LINE,
    )
    observed = ObservedReply(
        state="queued",
        role="system",
        body=WAITING_LINE,
        system_reason="visitor_request",
    )
    verdict = score_case(case, observed)
    assert verdict.passed is False
    assert "state: expected bot, got queued" in verdict.failures
    assert any("copy:" in item for item in verdict.failures)


def test_grounded_turnaround_fails_if_reply_mentions_documents() -> None:
    case = EvalCase(
        id="grounded.turnaround",
        family="grounded.turnaround",
        turns=("how fast are results",),
        expected_state="bot",
        must_contain=("24-48",),
        must_not_contain=("documents",),
    )
    observed = ObservedReply(
        state="bot",
        role="bot",
        body="Based on the documents, most negatives are reported within 24-48 hours.",
        system_reason="answer",
    )
    verdict = score_case(case, observed)
    assert verdict.passed is False
    assert "must_not_contain: documents" in verdict.failures
    assert all("24-48" not in item for item in verdict.failures)


def test_grounded_turnaround_fails_if_hours_claim_is_missing() -> None:
    case = EvalCase(
        id="grounded.turnaround",
        family="grounded.turnaround",
        turns=("how fast are results",),
        expected_state="bot",
        must_contain=("24-48",),
        must_not_contain=("documents",),
    )
    observed = ObservedReply(
        state="bot",
        role="bot",
        body="Results come back quickly for most employers.",
        system_reason="answer",
    )
    verdict = score_case(case, observed)
    assert verdict.passed is False
    assert "must_contain: 24-48" in verdict.failures


def test_in_scope_miss_must_offer_transfer_without_queuing() -> None:
    case = EvalCase(
        id="miss.unpublished_pricing",
        family="retrieval.miss",
        turns=("what is your unpublished internal pricing matrix",),
        expected_state="bot",
        expected_copy=TRANSFER_OFFER,
        expected_reason="insufficient",
    )
    observed = ObservedReply(
        state="bot",
        role="system",
        body=TRANSFER_OFFER,
        system_reason="insufficient",
    )
    verdict = score_case(case, observed)
    assert verdict.passed is True


def test_pricing_followup_fails_when_reply_is_the_turnaround_faq() -> None:
    case = EvalCase(
        id="followup.pricing_after_services",
        family="followup.pricing",
        turns=("what services do you offer?", "and the pricing?"),
        expected_state="bot",
        must_contain=("proposal",),
        must_not_contain=("$", "documents", "24-48"),
    )
    observed = ObservedReply(
        state="bot",
        role="bot",
        body=(
            "Most negative results are reported within 24-48 hours, and rapid "
            "eCup testing can deliver negatives in minutes."
        ),
        system_reason="answer",
    )
    verdict = score_case(case, observed)
    assert verdict.passed is False
    assert "must_contain: proposal" in verdict.failures
    assert "must_not_contain: 24-48" in verdict.failures
