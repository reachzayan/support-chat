import os
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.ws_helpers import (
    AGENT_HELP,
    AGENT_MESSAGE_ID,
    DOT_QUESTION,
    JOIN_LINE_ALEX,
    PRECHAT_SUBMISSION_ID,
    STAFF_ORIGIN,
    STILL_THERE,
    WIDGET_ORIGIN,
    auth_agent,
    auth_visitor,
    collect_until,
    conversation_state,
    decode_widget_token,
    frames_of_type,
    login_staff,
    message_count,
    post_bootstrap,
    seed_demo_world,
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://:local-dev-redis@127.0.0.1:56379/0")


def _redis_up() -> bool:
    try:
        import redis

        client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=1)
        try:
            return bool(client.ping())
        finally:
            client.close()
    except Exception:
        return False


def _require_redis() -> None:
    if not _redis_up():
        if os.environ.get("CI"):
            raise RuntimeError("Redis is required in CI")
        pytest.skip("Redis is down; skipping delivery tests")


def _prechat_and_join(client: TestClient) -> dict:
    seed_demo_world()
    boot = post_bootstrap(client)
    claims = decode_widget_token(boot.json()["bootstrap_token"])
    access_token = login_staff(client)
    return {
        "bootstrap_token": boot.json()["bootstrap_token"],
        "conversation_id": claims["conversation_id"],
        "access_token": access_token,
    }


def test_heartbeat_catch_up_delivers_committed_row_when_wakeup_suppressed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_redis()
    from app.chat.connection_manager import connection_manager

    ctx = _prechat_and_join(client)
    conversation_id = ctx["conversation_id"]
    monkeypatch.setattr(connection_manager, "suppress_wakeups", True)

    with client.websocket_connect("/ws/agent", headers={"Origin": STAFF_ORIGIN}) as agent:
        auth_agent(agent, ctx["access_token"])
        agent.send_json(
            {
                "v": 1,
                "type": "subscribe",
                "conversation_id": conversation_id,
                "last_event_id": 0,
            }
        )
        with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
            auth_visitor(visitor, ctx["bootstrap_token"])
            collect_until(
                visitor, lambda frames: any(frame.get("type") == "state" for frame in frames)
            )
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
            collect_until(
                visitor,
                lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
            )
            agent.send_json({"v": 1, "type": "join", "conversation_id": conversation_id})
            collect_until(
                agent,
                lambda frames: any(
                    (frame.get("type") == "state" and frame.get("state") == "human")
                    or (frame.get("type") == "message" and frame.get("body") == JOIN_LINE_ALEX)
                    for frame in frames
                ),
            )
            # Join may not have been delivered to the visitor socket because wakeups are suppressed.
            visitor.send_json({"v": 1, "type": "heartbeat"})
            join_catchup = collect_until(
                visitor,
                lambda frames: any(
                    frame.get("type") == "message" and frame.get("body") == JOIN_LINE_ALEX
                    for frame in frames
                ),
            )
            join_rows = [
                frame
                for frame in join_catchup
                if frame.get("type") == "message" and frame.get("body") == JOIN_LINE_ALEX
            ]
            assert len(join_rows) == 1
            agent.send_json(
                {
                    "v": 1,
                    "type": "message",
                    "conversation_id": conversation_id,
                    "client_message_id": AGENT_MESSAGE_ID,
                    "body": AGENT_HELP,
                }
            )
            collect_until(agent, lambda frames: any(frame.get("type") == "ack" for frame in frames))
            visitor.send_json({"v": 1, "type": "heartbeat"})
            help_frames = collect_until(
                visitor,
                lambda frames: any(
                    frame.get("type") == "message" and frame.get("body") == AGENT_HELP
                    for frame in frames
                ),
            )

    help_rows = [
        frame
        for frame in help_frames
        if frame.get("type") == "message" and frame.get("body") == AGENT_HELP
    ]
    assert len(help_rows) == 1
    assert help_rows[0]["role"] == "agent"
    assert message_count(uuid.UUID(conversation_id), body=AGENT_HELP) == 1
    assert conversation_state(uuid.UUID(conversation_id)) == "human"


def test_reconnect_after_cursor_11_replays_only_later_ids_then_state(
    client: TestClient,
) -> None:
    _require_redis()
    ctx = _prechat_and_join(client)
    conversation_id = ctx["conversation_id"]

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, ctx["bootstrap_token"])
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
        collect_until(
            visitor,
            lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
        )
        for index in range(12):
            visitor.send_json(
                {
                    "v": 1,
                    "type": "message",
                    "client_message_id": str(uuid.UUID(int=index + 2)),
                    "body": f"context {index + 2}",
                }
            )
            collect_until(
                visitor, lambda frames: any(frame.get("type") == "ack" for frame in frames)
            )

    # 1 welcome + 1 prechat visitor + 1 miss offer + 12 later visitors + 12 off-topic replies
    assert message_count(uuid.UUID(conversation_id)) == 27
    assert message_count(uuid.UUID(conversation_id), role="system") == 14

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, ctx["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json({"v": 1, "type": "resume", "last_event_id": 11})
        replayed = collect_until(
            visitor,
            lambda frames: (
                any(frame.get("type") == "state" for frame in frames)
                and any(
                    frame.get("type") == "message" and frame.get("id") == 27 for frame in frames
                )
            ),
        )

    messages = frames_of_type(replayed, "message")
    ids = [frame["id"] for frame in messages]
    assert ids == list(range(12, 28))
    assert all(message_id > 11 for message_id in ids)
    assert frames_of_type(replayed, "state")[-1]["state"] == "bot"
    assert message_count(uuid.UUID(conversation_id), body=STILL_THERE) == 0
    assert message_count(uuid.UUID(conversation_id), body=DOT_QUESTION) == 1
