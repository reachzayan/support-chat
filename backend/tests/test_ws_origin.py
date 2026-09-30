import json

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    BG_PUBLIC_KEY,
    BG_SITE_KEY,
    DEMO_GREETING,
    DEMO_NAME,
    DEMO_PRIVACY,
    DEMO_PUBLIC_KEY,
    DEMO_SITE_KEY,
    DOT_QUESTION,
    EASY_PUBLIC_KEY,
    EASY_SITE_KEY,
    EVIL_ORIGIN,
    HOST_ORIGIN,
    PRECHAT_SUBMISSION_ID,
    STAFF_ORIGIN,
    WIDGET_ORIGIN,
    auth_agent,
    auth_visitor,
    bootstrap_payload,
    collect_until,
    conversation_count,
    conversation_id_from_state,
    decode_widget_token,
    insert_site,
    insert_staff,
    login_staff,
    post_bootstrap,
    seed_demo_world,
    visitor_count,
)


def test_allowed_host_bootstrap_returns_widget_config_and_scoped_token(
    client: TestClient,
) -> None:
    seed_demo_world()

    response = post_bootstrap(client)

    assert response.status_code == 200
    body = response.json()
    assert body["widget"] == {
        "name": DEMO_NAME,
        "greeting": DEMO_GREETING,
        "privacy_url": DEMO_PRIVACY,
        "bot_enabled": True,
        "human_enabled": True,
        "contact_info": [],
    }
    assert body["resume_token"]
    claims = decode_widget_token(body["bootstrap_token"])
    assert claims["parent_origin"] == HOST_ORIGIN
    assert claims["site_id"]
    assert claims["visitor_id"]
    assert "conversation_id" not in claims
    assert response.headers["access-control-allow-origin"] == HOST_ORIGIN
    assert "origin" in response.headers["vary"].lower()
    assert response.headers["cache-control"] == "no-store"
    assert visitor_count() == 1
    assert conversation_count() == 0


def test_new_bootstrap_snapshot_is_empty_prechat(client: TestClient) -> None:
    seed_demo_world()

    body = post_bootstrap(client).json()

    claims = decode_widget_token(body["bootstrap_token"])
    assert body["mode"] == "conversation"
    assert "conversation_id" not in claims
    assert body["conversation"] == {
        "state": "prechat",
        "assigned_agent": None,
        "messages": [],
        "has_older": False,
    }
    assert conversation_count() == 0


def test_resume_bootstrap_snapshot_includes_the_visitor_line(client: TestClient) -> None:
    seed_demo_world()
    first = post_bootstrap(client)
    resume = first.json()["resume_token"]
    token = first.json()["bootstrap_token"]

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, token)
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": PRECHAT_SUBMISSION_ID,
                "name": "Ada Lopez",
                "email": "ada@example.com",
                "phone": "",
                "inquiry_type": "results",
                "message": DOT_QUESTION,
            }
        )
        accepted = collect_until(
            visitor,
            lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
        )
        conversation_id = conversation_id_from_state(accepted)
        collect_until(
            visitor,
            lambda frames: any(
                frame.get("type") == "message" and frame.get("role") == "bot" for frame in frames
            ),
        )

    resume_response = post_bootstrap(
        client,
        {
            **bootstrap_payload(resume_token=resume),
            "action": "open",
            "conversation_id": conversation_id,
        },
    )
    assert resume_response.status_code == 200, resume_response.text
    body = resume_response.json()
    conversation = body["conversation"]
    bodies = [
        frame["body"]
        for frame in conversation["messages"]
        if frame.get("type") == "message" and frame.get("role") == "visitor"
    ]

    assert conversation["state"] == "bot"
    assert conversation["assigned_agent"] is None
    assert bodies == [DOT_QUESTION]


def test_evil_missing_and_null_origin_create_zero_visitors(client: TestClient) -> None:
    seed_demo_world()

    evil = post_bootstrap(client, origin=EVIL_ORIGIN)
    missing = post_bootstrap(client, origin=None)
    null_origin = post_bootstrap(client, extra_headers={"Origin": "null"})

    assert evil.status_code == 403
    assert missing.status_code == 403
    assert null_origin.status_code == 403
    assert visitor_count() == 0


def test_site_a_resume_token_on_site_b_exposes_no_site_a_identity(client: TestClient) -> None:
    easy_id = insert_site(EASY_SITE_KEY, "SampleSite", EASY_PUBLIC_KEY)
    insert_site(BG_SITE_KEY, "Sample Services", BG_PUBLIC_KEY)

    easy = post_bootstrap(
        client,
        bootstrap_payload(EASY_SITE_KEY, EASY_PUBLIC_KEY),
    )
    assert easy.status_code == 200
    easy_claims = decode_widget_token(easy.json()["bootstrap_token"])
    easy_resume = easy.json()["resume_token"]

    other = post_bootstrap(
        client,
        bootstrap_payload(BG_SITE_KEY, BG_PUBLIC_KEY, resume_token=easy_resume),
    )
    assert other.status_code == 200
    other_body = other.json()
    other_claims = decode_widget_token(other_body["bootstrap_token"])

    assert visitor_count(easy_id) == 1
    assert conversation_count() == 0
    assert other_claims["visitor_id"] != easy_claims["visitor_id"]
    assert "conversation_id" not in easy_claims
    assert "conversation_id" not in other_claims
    assert other_claims["site_id"] != easy_claims["site_id"]
    dumped = json.dumps(other_body)
    assert easy_claims["visitor_id"] not in dumped
    assert easy_resume not in dumped


def test_unknown_site_and_public_key_mismatch_return_the_same_404(
    client: TestClient,
) -> None:
    seed_demo_world()

    unknown = post_bootstrap(client, bootstrap_payload("missing", DEMO_PUBLIC_KEY))
    mismatch = post_bootstrap(client, bootstrap_payload(DEMO_SITE_KEY, "z" * 64))

    assert unknown.status_code == 404
    assert mismatch.status_code == 404
    assert unknown.json() == mismatch.json()
    assert "SampleSite" not in unknown.text
    assert DEMO_NAME not in unknown.text
    assert visitor_count() == 0


def test_agent_socket_rejects_missing_and_widget_origin_before_auth(
    client: TestClient,
) -> None:
    seed_demo_world()

    with pytest.raises(WebSocketDisconnect) as missing:
        with client.websocket_connect("/ws/agent"):
            pass
    assert missing.value.code == 4403

    with pytest.raises(WebSocketDisconnect) as widget:
        with client.websocket_connect("/ws/agent", headers={"Origin": WIDGET_ORIGIN}):
            pass
    assert widget.value.code == 4403


def test_visitor_bootstrap_token_cannot_authenticate_agent_socket(
    client: TestClient,
) -> None:
    seed_demo_world()
    boot = post_bootstrap(client)
    token = boot.json()["bootstrap_token"]

    with client.websocket_connect("/ws/agent", headers={"Origin": STAFF_ORIGIN}) as websocket:
        websocket.send_json({"v": 1, "type": "auth", "access_token": token})
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
        assert closed.value.code == 4401


def test_expired_staff_token_closes_agent_socket_4401(client: TestClient) -> None:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    stale = jwt.encode(
        {"sub": "00000000-0000-4000-8000-000000000099", "token_version": 0, "exp": 1},
        "t" * 64,
        algorithm="HS256",
    )

    with client.websocket_connect("/ws/agent", headers={"Origin": STAFF_ORIGIN}) as websocket:
        websocket.send_json({"v": 1, "type": "auth", "access_token": stale})
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
        assert closed.value.code == 4401


def test_visitor_socket_rejects_staff_origin(client: TestClient) -> None:
    seed_demo_world()
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/ws/visitor", headers={"Origin": HOST_ORIGIN}):
            pass
    assert closed.value.code == 4403


def test_logout_closes_agent_socket_on_ping(client: TestClient) -> None:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    access = login_staff(client)
    csrf = client.cookies.get("supportchat_csrf")
    assert csrf
    with client.websocket_connect("/ws/agent", headers={"Origin": STAFF_ORIGIN}) as agent:
        auth_agent(agent, access)
        logout = client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
        assert logout.status_code == 200
        agent.send_json({"v": 1, "type": "ping"})
        with pytest.raises(WebSocketDisconnect) as closed:
            agent.receive_json()
        assert closed.value.code == 4401


def test_visitor_array_json_returns_invalid_without_dropping_the_socket(
    client: TestClient,
) -> None:
    seed_demo_world()
    boot = post_bootstrap(client)
    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, boot.json()["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_text("[]")
        frames = collect_until(
            visitor, lambda items: any(item.get("type") == "error" for item in items)
        )
        errors = [item for item in frames if item.get("type") == "error"]
        assert errors[-1]["code"] == "invalid"
        visitor.send_json({"v": 1, "type": "ping"})
        pong = collect_until(
            visitor, lambda items: any(item.get("type") == "pong" for item in items)
        )
        assert any(item.get("type") == "pong" for item in pong)


def test_bootstrap_body_over_8kib_is_400_and_creates_zero_visitors(client: TestClient) -> None:
    insert_site(DEMO_SITE_KEY, "Demo", DEMO_PUBLIC_KEY)
    huge_key = "k" * 9000
    response = post_bootstrap(
        client,
        {"site_key": huge_key, "public_key": DEMO_PUBLIC_KEY},
    )
    assert response.status_code == 400
    assert visitor_count() == 0
