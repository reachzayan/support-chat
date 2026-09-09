import pytest

from app.chat.state_machine import IllegalTransition, apply_event

LEGAL = [
    (None, "start_prechat", "prechat"),
    ("prechat", "submit_prechat", "bot"),
    ("prechat", "capture", "queued"),
    ("bot", "visitor_message", "bot"),
    ("bot", "bot_reply", "bot"),
    ("bot", "escalate", "queued"),
    ("bot", "join", "human"),
    ("queued", "visitor_message", "queued"),
    ("queued", "join", "human"),
    ("queued", "close_attention", "closed"),
    ("human", "visitor_message", "human"),
    ("human", "agent_message", "human"),
    ("human", "transfer_to_bot", "bot"),
    ("bot", "end", "closed"),
    ("queued", "end", "closed"),
    ("human", "end", "closed"),
    ("prechat", "end", "closed"),
]


@pytest.mark.parametrize(("start", "event", "expected"), LEGAL)
def test_legal_transitions(start: str | None, event: str, expected: str) -> None:
    assert apply_event(start, event) == expected


def test_join_from_bot_becomes_human() -> None:
    assert apply_event("bot", "join") == "human"


def test_bot_reply_is_illegal_outside_bot() -> None:
    for state in ("queued", "human", "closed", "prechat", None):
        with pytest.raises(IllegalTransition):
            apply_event(state, "bot_reply")


def test_agent_message_is_illegal_outside_human() -> None:
    for state in (None, "prechat", "bot", "queued", "closed"):
        with pytest.raises(IllegalTransition):
            apply_event(state, "agent_message")


def test_transfer_to_bot_is_illegal_outside_human() -> None:
    for state in (None, "prechat", "bot", "queued", "closed"):
        with pytest.raises(IllegalTransition):
            apply_event(state, "transfer_to_bot")


def test_second_prechat_is_illegal() -> None:
    with pytest.raises(IllegalTransition):
        apply_event("bot", "start_prechat")
    with pytest.raises(IllegalTransition):
        apply_event("prechat", "start_prechat")
    with pytest.raises(IllegalTransition):
        apply_event("bot", "submit_prechat")


def test_no_event_after_closed() -> None:
    for event in (
        "start_prechat",
        "submit_prechat",
        "visitor_message",
        "bot_reply",
        "escalate",
        "join",
        "agent_message",
        "transfer_to_bot",
        "end",
    ):
        with pytest.raises(IllegalTransition):
            apply_event("closed", event)
