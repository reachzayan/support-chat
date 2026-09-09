class IllegalTransition(Exception):
    pass


_TRANSITIONS: dict[tuple[str | None, str], str] = {
    (None, "start_prechat"): "prechat",
    ("prechat", "submit_prechat"): "bot",
    ("prechat", "capture"): "queued",
    ("bot", "visitor_message"): "bot",
    ("bot", "bot_reply"): "bot",
    ("bot", "escalate"): "queued",
    ("bot", "join"): "human",
    ("queued", "visitor_message"): "queued",
    ("queued", "join"): "human",
    ("queued", "close_attention"): "closed",
    ("human", "visitor_message"): "human",
    ("human", "agent_message"): "human",
    ("human", "transfer_to_bot"): "bot",
    ("bot", "end"): "closed",
    ("queued", "end"): "closed",
    ("human", "end"): "closed",
    ("prechat", "end"): "closed",
}


def apply_event(state: str | None, event: str) -> str:
    next_state = _TRANSITIONS.get((state, event))
    if next_state is None:
        raise IllegalTransition(f"{state}+{event}")
    return next_state
