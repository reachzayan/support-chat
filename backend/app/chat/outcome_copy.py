"""Per-outcome visitor copy for grounded serving and human handoff."""

from __future__ import annotations

WAITING_LINE = "A specialist will join this chat shortly."
CALLBACK_LINE = "A representative will contact you in 24 hours."
TRANSFER_OFFER = (
    "Sorry, I can't answer this question, may I transfer you to one of our representatives?"
)
CONTACT_OFFER = (
    "I want to get you an accurate answer. "
    "Would you like to be contacted by one of our representatives?"
)
KEEP_HELPING_LINE = "I can help with screening and compliance questions here. What do you need?"
GREET_LINE = "Hi. I can help with screening and compliance questions. What do you need?"
THANKS_LINE = "You're welcome. Anything else on screening or compliance?"
BYE_LINE = "Take care. Come back if you have screening or compliance questions."
DISENGAGE_LINE = "Sorry, I can't engage in this. If you don't have anymore questions I am going to close this chat now"
OFF_TOPIC_LINE = "I can't help with that here."

INSUFFICIENT_HUMAN = "I want to get you an accurate answer. A specialist can pick up here."
INSUFFICIENT_SOLO = "I want to get you an accurate answer."
TECH_FAIL_HUMAN = "Sorry, I hit a temporary issue. A specialist can take it from here."
TECH_FAIL_SOLO = "Sorry, I hit a temporary issue. We'll follow up shortly."
POLICY_BOUNDARY = (
    "I can't share that in chat. A specialist can walk you through it in the right channel."
)
OUT_OF_SCOPE = "I can't help with that here."

VISITOR_REQUEST_HUMAN = WAITING_LINE
SENSITIVE_HUMAN = "A specialist can help through a secure channel."
INDIVIDUAL_CASE_HUMAN = "A specialist is required to discuss an individual's case. Joining you now."
RETRIEVAL_MISS_HUMAN = INSUFFICIENT_HUMAN
SUFFICIENCY_FAIL_HUMAN = (
    "I don't have enough information here to answer that safely. A specialist can help."
)
PROVIDER_TIMEOUT_HUMAN = TECH_FAIL_HUMAN
REPEATED_MISS_HUMAN = "Let me hand you to a specialist so you don't have to repeat yourself."
RATE_CEILING_HUMAN = "I've hit a temporary limit. A specialist can take over now."
OFF_TOPIC_HUMAN = OUT_OF_SCOPE

_LEGACY_OUTCOMES = frozenset({"insufficient", "tech_fail", "policy_boundary", "out_of_scope"})
_GREET_TOKENS = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "yo",
        "hiya",
        "howdy",
        "morning",
        "afternoon",
        "evening",
        "welcome",
    }
)
_THANKS_TOKENS = frozenset({"thanks", "thank", "cheers", "np"})
_BYE_TOKENS = frozenset({"bye", "goodbye", "cya", "later", "goodnight"})


def chitchat_reply(text: str) -> str | None:
    from app.services.kb_tokens import tokenize

    tokens = set(tokenize(text))
    if not tokens:
        return None
    if tokens <= _GREET_TOKENS:
        return GREET_LINE
    if tokens <= _THANKS_TOKENS:
        return THANKS_LINE
    if tokens <= _BYE_TOKENS:
        return BYE_LINE
    return None


def callback_line(window_hours: int) -> str:
    hours = max(1, int(window_hours))
    if hours == 24:
        return CALLBACK_LINE
    unit = "hour" if hours == 1 else "hours"
    return f"A representative will contact you in {hours} {unit}."


def transfer_offer_line(*, human_enabled: bool) -> str:
    if human_enabled:
        return TRANSFER_OFFER
    return CONTACT_OFFER


def is_transfer_offer_body(body: str) -> bool:
    return body in {TRANSFER_OFFER, CONTACT_OFFER}


def follow_up_line(*, human_enabled: bool, window_hours: int = 24) -> str:
    if human_enabled:
        return WAITING_LINE
    return callback_line(window_hours)


def visitor_copy(
    outcome: str,
    *,
    human_enabled: bool,
    window_hours: int = 24,
) -> str:
    """Return visitor-facing copy for a sufficiency or escalation outcome."""
    if outcome in _LEGACY_OUTCOMES:
        return _legacy_copy(outcome, human_enabled=human_enabled, window_hours=window_hours)
    return handoff_copy(outcome, human_enabled=human_enabled, window_hours=window_hours)


def handoff_copy(  # noqa: C901
    reason: str,
    *,
    human_enabled: bool,
    window_hours: int = 24,
) -> str:
    callback = callback_line(window_hours)
    if reason == "visitor_request":
        return WAITING_LINE if human_enabled else callback
    if reason == "sensitive":
        return SENSITIVE_HUMAN if human_enabled else callback
    if reason == "individual_case":
        if human_enabled:
            return INDIVIDUAL_CASE_HUMAN
        return "A specialist is required to discuss an individual's case. " + callback
    if reason == "retrieval_miss":
        if human_enabled:
            return RETRIEVAL_MISS_HUMAN
        return "I want to get you an accurate answer. " + callback
    if reason == "sufficiency_fail":
        if human_enabled:
            return SUFFICIENCY_FAIL_HUMAN
        return "I don't have enough information here to answer that safely. " + callback
    if reason == "provider_timeout":
        if human_enabled:
            return PROVIDER_TIMEOUT_HUMAN
        return "Sorry, I hit a temporary issue. " + callback
    if reason == "repeated_miss":
        if human_enabled:
            return REPEATED_MISS_HUMAN
        return "Let me hand you to a specialist so you don't have to repeat yourself. " + callback
    if reason == "policy_boundary":
        if human_enabled:
            return POLICY_BOUNDARY
        return "I can't share that in chat. " + callback
    if reason == "rate_ceiling":
        if human_enabled:
            return RATE_CEILING_HUMAN
        return "I've hit a temporary limit. " + callback
    if reason == "off_topic":
        return OFF_TOPIC_LINE
    raise ValueError(f"unsupported handoff copy: {reason}")


def _legacy_copy(outcome: str, *, human_enabled: bool, window_hours: int) -> str:
    if outcome == "insufficient":
        return handoff_copy(
            "retrieval_miss", human_enabled=human_enabled, window_hours=window_hours
        )
    if outcome == "tech_fail":
        return handoff_copy(
            "provider_timeout", human_enabled=human_enabled, window_hours=window_hours
        )
    if outcome == "policy_boundary":
        return handoff_copy(
            "policy_boundary", human_enabled=human_enabled, window_hours=window_hours
        )
    if outcome == "out_of_scope":
        return handoff_copy("off_topic", human_enabled=human_enabled, window_hours=window_hours)
    raise ValueError(f"unsupported outcome copy: {outcome}")
