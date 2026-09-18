"""Temporary evaluation must preserve real chat behavior and access boundaries."""

from uuid import uuid4

import pytest

from app.main import app
from app.models.user import User
from app.security.deps import get_current_admin
from tests.ws_helpers import insert_site, message_count

PATH = "/api/internal/eval/turn"


@pytest.fixture
def evaluation(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_EVAL_ENABLED", "true")
    app.dependency_overrides[get_current_admin] = lambda: User(id=uuid4(), is_admin=True)
    insert_site("data", "Sample Data Services", "data-public")
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def test_enabled_endpoint_requires_staff_authentication(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_EVAL_ENABLED", "true")
    response = client.post(PATH, json={"site_key": "data", "message": "hello"})
    assert response.status_code == 401


def test_eval_turns_persist_history_and_do_not_replay_old_replies(evaluation):
    first = evaluation.post(PATH, json={"site_key": "data", "message": "hello"})
    assert first.status_code == 200, first.text
    payload = first.json()
    conversation_id = payload["conversation_id"]
    assert payload["state"] == "bot"
    assert [m["role"] for m in payload["messages"]] == ["visitor", "system"]
    assert payload["trace"]["classification"]["chitchat"] is True
    assert payload["trace"]["classification"]["sensitive_category"] == "none"
    assert payload["messages"][1]["body"] == "Hi. How can we help you today?"
    assert payload["trace"]["decision"]["decision"]["reason_code"] == "chitchat"
    assert payload["trace"]["final"]["persisted"] is True
    assert payload["trace"]["final"]["state"] == "bot"
    assert first.headers["cache-control"] == "no-store"
    queued = evaluation.post(
        PATH,
        json={
            "site_key": "data",
            "conversation_id": conversation_id,
            "message": "I want to speak to a human",
        },
    )
    assert queued.status_code == 200, queued.text
    assert queued.json()["state"] == "queued"
    assert queued.json()["trace"]["decision"]["decision"]["reason_code"] == "visitor_request"
    assert queued.json()["trace"]["handoff_summary"]["status"] == "fallback"
    assert queued.json()["trace"]["handoff_summary"]["persisted"] is True
    after = evaluation.post(
        PATH,
        json={
            "site_key": "data",
            "conversation_id": conversation_id,
            "message": "Some additional context for the specialist",
        },
    )
    assert after.status_code == 200, after.text
    assert [m["role"] for m in after.json()["messages"]] == ["visitor"]
    assert after.json()["trace"]["decision"]["decision"]["reason_code"] == "not_bot_state"
    assert message_count(role="visitor") == 3
    assert message_count(role="bot") == 0


def test_eval_sensitive_early_exit_has_a_final_decision(evaluation):
    response = evaluation.post(PATH, json={"site_key": "data", "message": "My SSN is 123-45-6789"})
    assert response.status_code == 200, response.text
    trace = response.json()["trace"]
    assert trace["decision"]["decision"]["reason_code"] == "policy_sensitive"
    assert trace["decision"]["decision"]["outcome"] == "boundary"
    assert trace["final"]["persisted"] is True
    assert trace["final"]["reply_ids"] == [
        m["id"] for m in response.json()["messages"] if m["role"] != "visitor"
    ]


def test_eval_waits_for_summary_provider_and_persistence(evaluation, monkeypatch):
    from types import SimpleNamespace

    summary = "The visitor requested a human specialist. The chat was queued."
    calls = []

    class Messages:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(text=summary)],
                stop_reason="end_turn",
                _request_id="summary-fixture",
                usage=None,
            )

    class Client:
        def __init__(self, **kwargs):
            self.messages = Messages()

        async def close(self):
            pass

    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-provider-key")
    monkeypatch.setattr("app.services.handoff_summary.AsyncAnthropic", Client)
    response = evaluation.post(PATH, json={"site_key": "data", "message": "Human please"})
    assert response.status_code == 200, response.text
    trace = response.json()["trace"]
    assert len(calls) == 1
    assert trace["handoff_summary"]["body"] == summary
    assert trace["handoff_summary"]["status"] == "completed"
    assert trace["handoff_summary"]["persisted"] is True
    assert trace["handoff_summary_provider_1"]["request_id"] == "summary-fixture"
    assert trace["background_work"]["pending"] == 0
    from sqlalchemy import select

    from app.models.handoff_context import HandoffContext
    from tests.ws_helpers import sync_session

    sessions = sync_session()
    session = next(sessions)
    try:
        stored = session.scalar(select(HandoffContext))
        assert stored.machine_summary == summary
    finally:
        sessions.close()


def test_eval_summary_failure_records_both_attempts_and_persisted_fallback(evaluation, monkeypatch):
    class Messages:
        async def create(self, **kwargs):
            raise TimeoutError("synthetic timeout")

    class Client:
        def __init__(self, **kwargs):
            self.messages = Messages()

        async def close(self):
            pass

    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-provider-key")
    monkeypatch.setattr("app.services.handoff_summary.AsyncAnthropic", Client)
    response = evaluation.post(PATH, json={"site_key": "data", "message": "Human please"})
    assert response.status_code == 200, response.text
    trace = response.json()["trace"]
    assert trace["handoff_summary"]["status"] == "fallback"
    assert trace["handoff_summary"]["persisted"] is True
    for attempt in (1, 2):
        assert trace[f"handoff_summary_provider_{attempt}"]["error_class"] == "TimeoutError"


def test_eval_duplicate_has_final_trace_without_replaying_greeting(evaluation):
    client_message_id = str(uuid4())
    payload = {"site_key": "data", "message": "hello", "client_message_id": client_message_id}
    first = evaluation.post(PATH, json=payload)
    assert first.status_code == 200, first.text
    payload["conversation_id"] = first.json()["conversation_id"]
    duplicate = evaluation.post(PATH, json=payload)
    assert duplicate.status_code == 200, duplicate.text
    trace = duplicate.json()["trace"]
    assert duplicate.json()["messages"] == []
    assert trace["decision"]["decision"]["reason_code"] == "duplicate"
    assert trace["final"]["reply_persisted"] is False


def test_eval_cannot_resume_another_sites_conversation(evaluation):
    insert_site("other", "Other brand", "other-public")
    first = evaluation.post(PATH, json={"site_key": "data", "message": "hello"})
    assert first.status_code == 200, first.text
    foreign = evaluation.post(
        PATH,
        json={
            "site_key": "other",
            "conversation_id": first.json()["conversation_id"],
            "message": "hello",
        },
    )
    assert foreign.status_code == 404
    assert message_count(role="visitor") == 1


def test_eval_rejects_blank_and_oversize_messages(evaluation):
    for message in ("  ", "x" * 4001):
        response = evaluation.post(PATH, json={"site_key": "data", "message": message})
        assert response.status_code == 422
    assert message_count() == 0


def test_eval_rate_limit_is_retryable_without_losing_conversation(evaluation, monkeypatch):
    monkeypatch.setenv("RATE_VISITOR_SUBMIT_IP", "1")
    first = evaluation.post(PATH, json={"site_key": "data", "message": "hello"})
    assert first.status_code == 200, first.text
    blocked = evaluation.post(
        PATH,
        json={
            "site_key": "data",
            "conversation_id": first.json()["conversation_id"],
            "message": "hello again",
        },
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
    assert blocked.json()["conversation_id"] == first.json()["conversation_id"]
    assert message_count(role="visitor") == 1


def test_eval_trace_preserves_the_complete_retrieval_query(evaluation):
    response = evaluation.post(
        PATH,
        json={
            "site_key": "data",
            "message": (
                "What does SampleMail Plus do for a creditor rights law firm? "
                "We have a physical mail workflow with many returned demand letters. "
                "Please explain address verification, how the address refresh differs from "
                "standard SampleMail, and whether we can track delivery through a portal."
            ),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["trace"]["retrieval"]["query"] == (
        "What does SampleMail Plus do for a creditor rights law firm? "
        "We have a physical mail workflow with many returned demand letters. "
        "Please explain address verification, how the address refresh differs from "
        "standard SampleMail, and whether we can track delivery through a portal."
    )
