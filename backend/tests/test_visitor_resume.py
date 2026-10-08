import json
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.visitor import Visitor
from app.services.conversation_input import hash_resume_token
from tests.ws_helpers import (
    DEMO_PUBLIC_KEY,
    DEMO_SITE_KEY,
    HOST_ORIGIN,
    PRECHAT_SUBMISSION_ID,
    WIDGET_ORIGIN,
    auth_visitor,
    bootstrap_payload,
    collect_until,
    conversation_id_from_state,
    decode_widget_token,
    post_bootstrap,
    seed_demo_world,
    sync_session,
)


def _activate(
    client: TestClient,
    *,
    name: str = "Ada Lopez",
    email: str = "ada.lopez@example.com",
    phone: str = "+1 202 555 0198",
) -> tuple[str, str, str]:
    first = post_bootstrap(client)
    assert first.status_code == 200
    body = first.json()
    claims = decode_widget_token(body["bootstrap_token"])
    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, body["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": PRECHAT_SUBMISSION_ID,
                "name": name,
                "email": email,
                "phone": phone,
                "inquiry_type": "results",
                "message": "",
            }
        )
        started = collect_until(
            visitor,
            lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
        )
        conversation_id = conversation_id_from_state(started)
    return body["resume_token"], claims["visitor_id"], conversation_id


def _request(client: TestClient, resume: str, action: str, **extra: object):
    return post_bootstrap(
        client,
        {
            "site_key": DEMO_SITE_KEY,
            "public_key": DEMO_PUBLIC_KEY,
            "resume_token": resume,
            "action": action,
            **extra,
        },
    )


def _close(conversation_id: str, *, assigned_agent_id: uuid.UUID | None = None) -> None:
    session = next(sync_session())
    try:
        conversation = session.get(Conversation, uuid.UUID(conversation_id))
        assert conversation is not None
        conversation.state = "closed"
        conversation.closed_at = datetime.now(UTC)
        conversation.active_generation_id = None
        conversation.assigned_agent_id = assigned_agent_id
        session.commit()
    finally:
        session.close()


def test_returning_browser_gets_only_masked_identity_before_confirming(
    client: TestClient,
) -> None:
    seed_demo_world()
    resume, visitor_id, conversation_id = _activate(client)

    response = post_bootstrap(client, bootstrap_payload(resume_token=resume))

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "identity"
    assert body["identity"] == {
        "display_name": "Ada L.",
        "email_hint": "a•••@example.com",
        "phone_hint": "••• ••• 0198",
        "chat_count": 1,
    }
    assert "bootstrap_token" not in body
    assert "conversation" not in body
    dumped = json.dumps(body)
    assert visitor_id not in dumped
    assert conversation_id not in dumped
    assert "ada.lopez@example.com" not in dumped
    assert "+1 202 555 0198" not in dumped


def test_confirmed_history_is_metadata_only_and_scoped_to_the_token_owner(
    client: TestClient,
) -> None:
    seed_demo_world()
    resume_a, _, conversation_a = _activate(client)
    _, _, conversation_b = _activate(client, name="Ben Ortiz", email="ben@example.com", phone="")

    session = next(sync_session())
    try:
        session.add(
            Message(
                conversation_id=uuid.UUID(conversation_a),
                role="visitor",
                body="What records are included in a screening?",
                client_message_id=uuid.uuid4(),
            )
        )
        session.commit()
    finally:
        session.close()

    response = _request(client, resume_a, "history")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "history"
    assert [item["id"] for item in body["conversations"]] == [conversation_a]
    assert body["conversations"][0]["state"] == "bot"
    assert body["conversations"][0]["inquiry_type"] == "results"
    assert body["conversations"][0]["is_current"] is True
    assert body["conversations"][0]["preview"] == "What records are included in a screening?"
    assert "messages" not in body["conversations"][0]
    assert conversation_b not in json.dumps(body)

    forbidden = _request(client, resume_a, "open", conversation_id=conversation_b)
    assert forbidden.status_code == 404
    assert forbidden.json() == {"detail": "Not found"}


def test_refresh_closed_chat_keeps_it_closed_without_resuming(
    client: TestClient,
) -> None:
    seed_demo_world()
    resume, _, conversation_id = _activate(client)
    _close(conversation_id)

    response = _request(client, resume, "refresh", conversation_id=conversation_id)

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "conversation"
    assert body["conversation"]["id"] == conversation_id
    assert body["conversation"]["state"] == "closed"
    assert all(
        message.get("body") != "This chat has been resumed."
        for message in body["conversation"]["messages"]
    )


def test_resume_closed_chat_reopens_it_without_restoring_the_old_assignment(
    client: TestClient,
) -> None:
    _, alex_id = seed_demo_world()
    resume, _, conversation_id = _activate(client)
    _close(conversation_id, assigned_agent_id=alex_id)

    response = _request(client, resume, "open", conversation_id=conversation_id)

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "conversation"
    assert body["conversation"]["id"] == conversation_id
    assert body["conversation"]["state"] == "bot"
    assert body["conversation"]["assigned_agent"] is None
    assert any(
        message.get("body") == "This chat has been resumed."
        for message in body["conversation"]["messages"]
    )


def test_reopen_after_reset_shows_saved_chats_instead_of_the_blank_form(
    client: TestClient,
) -> None:
    seed_demo_world()
    resume, visitor_id, conversation_id = _activate(client)
    reset = _request(client, resume, "reset")
    assert reset.status_code == 200
    assert decode_widget_token(reset.json()["bootstrap_token"])["visitor_id"] == visitor_id
    assert reset.json()["mode"] == "conversation"
    assert reset.json()["conversation"]["state"] == "prechat"
    assert "id" not in reset.json()["conversation"]
    assert reset.json()["conversation"]["visitor_profile"] == {
        "name": "Ada Lopez",
        "email": "ada.lopez@example.com",
        "phone": "+1 202 555 0198",
    }

    reopened = post_bootstrap(client, bootstrap_payload(resume_token=resume))

    assert reopened.status_code == 200
    body = reopened.json()
    assert body["mode"] == "identity"
    assert body["identity"] == {
        "display_name": "Ada L.",
        "email_hint": "a•••@example.com",
        "phone_hint": "••• ••• 0198",
        "chat_count": 1,
    }
    assert "conversation" not in body

    history = _request(client, resume, "history")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()["conversations"]] == [conversation_id]


def test_resuming_an_old_chat_requires_confirmation_before_replacing_an_active_chat(
    client: TestClient,
) -> None:
    seed_demo_world()
    resume, _, old_id = _activate(client)
    _close(old_id)
    fresh = _request(client, resume, "reset")
    assert fresh.status_code == 200
    fresh_body = fresh.json()
    assert "id" not in fresh_body["conversation"]

    # Turn the new draft into a real active chat so replacing it is consequential.
    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, fresh_body["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": "10000000-0000-4000-8000-000000000099",
                "name": "Ada Lopez",
                "email": "ada.lopez@example.com",
                "phone": "+1 202 555 0198",
                "inquiry_type": "other",
                "message": "",
            }
        )
        started = collect_until(
            visitor,
            lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
        )
        active_id = conversation_id_from_state(started)

    conflict = _request(client, resume, "open", conversation_id=old_id)
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "Active chat exists"}

    resumed = _request(
        client,
        resume,
        "open",
        conversation_id=old_id,
        replace_current=True,
    )
    assert resumed.status_code == 200
    assert resumed.json()["conversation"]["id"] == old_id

    session = next(sync_session())
    try:
        states = dict(
            session.execute(
                select(Conversation.id, Conversation.state).where(
                    Conversation.id.in_((uuid.UUID(old_id), uuid.UUID(active_id)))
                )
            ).all()
        )
    finally:
        session.close()
    assert states[uuid.UUID(old_id)] == "bot"
    assert states[uuid.UUID(active_id)] == "closed"


def test_forget_revokes_the_server_capability_and_reusing_it_starts_fresh(
    client: TestClient,
) -> None:
    seed_demo_world()
    resume, visitor_id, _ = _activate(client)

    forgotten = _request(client, resume, "forget")

    assert forgotten.status_code == 200
    assert forgotten.json()["mode"] == "forgotten"
    session = next(sync_session())
    try:
        visitor = session.get(Visitor, uuid.UUID(visitor_id))
        assert visitor is not None
        assert visitor.resume_token_hash != hash_resume_token(resume)
    finally:
        session.close()

    replay = post_bootstrap(client, bootstrap_payload(resume_token=resume))
    assert replay.status_code == 200
    body = replay.json()
    assert body["mode"] == "conversation"
    assert body["conversation"]["state"] == "prechat"
    assert body["resume_token"] != resume
    claims = decode_widget_token(body["bootstrap_token"])
    assert claims["visitor_id"] != visitor_id


def test_invalid_action_shape_is_rejected_without_creating_a_visitor(client: TestClient) -> None:
    seed_demo_world()

    response = post_bootstrap(
        client,
        {
            "site_key": DEMO_SITE_KEY,
            "public_key": DEMO_PUBLIC_KEY,
            "action": "open",
        },
        origin=HOST_ORIGIN,
    )

    assert response.status_code == 400
