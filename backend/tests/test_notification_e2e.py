"""Notification E2E: real network API, visitor/staff sockets, Postgres, workers and TLS push.

Oracle: the user's notification requirements and the public chat/API contracts.
Only the external vendor gateway is replaced; received wire payloads are independently
decrypted and VAPID-verified by Node. This does not claim browser/OS receipt.
"""

from collections import Counter
from uuid import uuid4

import pytest

from tests.notification_e2e_helpers import (
    NotificationStack,
    drained,
    eventually,
    prechat,
    receive,
    send,
    sql,
)
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    JORDAN_EMAIL,
    JORDAN_NAME,
    JORDAN_PASSWORD,
    insert_site,
    insert_staff,
    sync_session,
)


@pytest.fixture
def stack(migrated_db, tmp_path):
    instance = NotificationStack(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def staff(stack):
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    insert_staff(JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD)
    return stack.login(ALEX_EMAIL), stack.login(JORDAN_EMAIL)


def callback_site():
    from app.models.site import Site

    site_id = insert_site("careers", "Careers", "careers-key")
    session = next(sync_session())
    try:
        site = session.get(Site, site_id)
        site.bot_enabled = False
        site.human_enabled = False
        session.commit()
    finally:
        session.close()
    return site_id


def test_selected_example_reaches_the_encrypted_gateway_without_changing_inbox_or_preferences(
    stack,
):
    alex, _ = staff(stack)
    site = callback_site()
    _, endpoint = stack.subscribe(alex, "preview", silent=True)
    before = stack.feed(alex)
    preferences = stack.http.get("/api/notifications/preferences", headers=alex).json()
    preview = stack.http.get(
        "/api/notifications/push/preview",
        headers=alex,
        params={"site_id": str(site), "scenario": "visitor_message"},
    )
    assert preview.status_code == 200
    assert preview.json()["title"] == "Preview: Careers · New visitor reply"
    assert (
        stack.http.post(
            "/api/notifications/push/test",
            headers=alex,
            json={"endpoint": endpoint, "site_id": str(site), "scenario": "visitor_message"},
        ).status_code
        == 202
    )
    stack.start_worker()
    eventually(drained)
    delivered = stack.gateway.received()
    assert len(delivered) == 1
    payload = delivered[0]["payload"]
    assert {key: payload[key] for key in ("title", "body", "action_label")} == preview.json()
    assert payload["silent"] is True and payload["conversation_id"] is None
    assert stack.feed(alex) == before
    assert stack.http.get("/api/notifications/preferences", headers=alex).json() == preferences


def test_site_push_selection_delivers_bot_only_without_changing_in_app_activity(stack):
    """User choices apply over real sockets, durable jobs, and encrypted network sends."""
    alex, jordan = staff(stack)
    easy = insert_site("easy", "SampleSite", "easy-key")
    careers = callback_site()
    stack.subscribe(alex, "selected-bot")
    for site, enabled, kinds in [(easy, True, ["bot"]), (careers, False, ["needs_attention"])]:
        response = stack.http.put(
            "/api/notifications/preferences/push",
            headers=alex,
            json={"site_id": str(site), "enabled": enabled, "scenarios": kinds},
        )
        assert response.status_code == 200
    with stack.visitor("easy", "easy-key") as visitor, stack.agent(jordan) as agent:
        bot_chat = prechat(visitor)
        bot_feed = stack.feed(alex)
        assert bot_feed["items"] == [] and bot_feed["unread_count"] == 0
        assert bot_feed["latest_id"] is not None
        send(agent, type="join", conversation_id=bot_chat)
        receive(agent, "state", state="human")
    with stack.visitor("careers", "careers-key") as visitor:
        attention_chat = prechat(visitor)
    assert sql("SELECT count(*) FROM push_deliveries WHERE finished_at IS NULL") == [(1,)]
    stack.start_worker()
    eventually(drained)
    delivered = stack.gateway.received()
    assert [(row["payload"]["title"], row["payload"]["conversation_id"]) for row in delivered] == [
        ("SampleSite · New bot conversation", bot_chat)
    ]
    assert delivered[0]["payload"]["body"].endswith(
        "General inquiry\nA visitor started or resumed an assistant conversation. Open it to follow along."
    )
    assert (
        stack.http.put(
            "/api/notifications/preferences/push",
            headers=alex,
            json={"site_id": str(easy), "enabled": False, "scenarios": ["bot"]},
        ).status_code
        == 200
    )
    with stack.visitor("easy", "easy-key") as visitor:
        prechat(visitor)
    assert sql("SELECT count(*) FROM push_deliveries") == [(1,)]
    feed = stack.feed(alex)
    assert {(row["conversation_id"], row["scenario"]) for row in feed["items"]} == {
        (bot_chat, "live"),
        (attention_chat, "needs_attention"),
    }
    assert feed["unread_count"] == 2


def test_chat_events_reach_correct_staff_devices_and_read_state_stays_private(stack):
    """Catches a missing event, wrong recipient, leaked content or duplicate socket retry."""
    alex, jordan = staff(stack)
    easy = insert_site("easy", "SampleSite", "easy-key")
    careers = callback_site()
    for scenario in ("bot", "closed"):
        stack.preference(jordan, easy, scenario, True)
    stack.preference(jordan, careers, "closed", True)
    for site in (easy, careers):
        assert (
            stack.http.put(
                "/api/notifications/preferences/push",
                headers=jordan,
                json={
                    "site_id": str(site),
                    "enabled": True,
                    "scenarios": ["live", "bot", "needs_attention", "visitor_message", "closed"],
                },
            ).status_code
            == 200
        )
    alex_device, _ = stack.subscribe(alex, "alex")
    jordan_device, _ = stack.subscribe(jordan, "jordan")
    silent_device, _ = stack.subscribe(jordan, "jordan-silent", silent=True)
    stack.start_worker()

    with stack.visitor("easy", "easy-key") as visitor, stack.agent(alex) as agent:
        chat = prechat(visitor)
        eventually(drained)
        send(agent, type="join", conversation_id=chat)
        receive(agent, "state", state="human")
        eventually(drained)
        message_id = str(uuid4())
        send(visitor, type="message", client_message_id=message_id, body="secret visitor message")
        original = receive(visitor, "ack", client_message_id=message_id)
        send(visitor, type="message", client_message_id=message_id, body="secret visitor message")
        assert receive(visitor, "ack", client_message_id=message_id)["id"] == original["id"]
        eventually(drained)
        mine, theirs = stack.feed(alex), stack.feed(jordan)
        assert [item["scenario"] for item in mine["items"]] == ["visitor_message"]
        assert [item["scenario"] for item in theirs["items"]] == ["live", "bot"]
        assert (
            stack.http.post(
                f"/api/notifications/conversations/{chat}/read",
                headers=alex,
                json={"through_id": mine["latest_id"]},
            ).status_code
            == 204
        )
        assert stack.feed(alex)["unread_count"] == 0
        assert stack.feed(jordan)["unread_count"] == 2
        send(agent, type="end", conversation_id=chat)
        receive(agent, "state", state="closed")
    with stack.visitor("careers", "careers-key") as visitor, stack.agent(alex) as agent:
        callback_chat = prechat(visitor)
        eventually(drained)
        send(agent, type="close_attention", conversation_id=callback_chat)
        receive(agent, "state", state="closed")

    eventually(drained)
    mine, theirs = stack.feed(alex), stack.feed(jordan)
    assert mine["items"] == [] and theirs["items"] == []
    assert mine["unread_conversations"] == {} and theirs["unread_conversations"] == {}
    assert mine["unread_count"] == 0 and theirs["unread_count"] == 0
    delivered = stack.gateway.received()
    assert Counter(row["path"] for row in delivered) == {
        "/fcm/send/alex": 2,
        "/fcm/send/jordan": 5,
        "/fcm/send/jordan-silent": 5,
    }
    devices = {row["path"]: row["payload"]["subscription_id"] for row in delivered}
    assert devices == {
        "/fcm/send/alex": alex_device,
        "/fcm/send/jordan": jordan_device,
        "/fcm/send/jordan-silent": silent_device,
    }
    assert {
        row["payload"]["silent"] for row in delivered if row["path"] == "/fcm/send/jordan-silent"
    } == {True}
    assert "secret visitor message" not in str(delivered) and "visitor@example.com" not in str(
        delivered
    )


def test_handoff_line_busy_prompt_and_wait_choices_reach_visitor_over_real_websocket(stack):
    alex, _ = staff(stack)
    insert_site("wait", "Waiting", "wait-key")
    with stack.visitor("wait", "wait-key") as visitor:
        chat = prechat(visitor)
        send(
            visitor,
            type="message",
            client_message_id=str(uuid4()),
            body="I need to talk to a person",
        )
        line = receive(visitor, "message", body="A specialist will join this chat shortly.")
        assert line["role"] == "system" and line["system_reason"] == "visitor_request"
        receive(visitor, "state", state="queued")
        # Advance durable queue age, then let the real idle sweep/socket watch act.
        sql(
            "UPDATE conversations SET handoff_wait_started_at = now() - interval '5 minutes' WHERE id = %s",
            (chat,),
        )
        send(visitor, type="resume", last_event_id=line["id"])
        import json
        import time

        deadline = time.monotonic() + 25
        prompt = None
        while time.monotonic() < deadline:
            frame = json.loads(visitor.recv(timeout=max(0.1, deadline - time.monotonic())))
            assert frame.get("type") != "error", frame
            if frame.get("type") == "ping":
                send(visitor, type="pong")
            if (
                frame.get("body")
                == "Our agents are all currently busy right now. Would you like to wait?"
            ):
                prompt = frame
                break
        assert prompt is not None
        receive(visitor, "state", state="queued", handoff_wait_prompt_id=prompt["id"])
        send(visitor, type="handoff_wait_response", prompt_id=prompt["id"], choice="wait")
        receive(visitor, "message", body="Thanks for waiting. You're still in the queue.")
        receive(visitor, "handoff_wait_accepted")
        assert sql(
            "SELECT state, handoff_wait_prompt_id FROM conversations WHERE id = %s", (chat,)
        ) == [("queued", None)]
        assert stack.feed(alex)["unread_conversations"] == {chat: 1}
        sql(
            "UPDATE conversations SET handoff_wait_started_at = now() - interval '5 minutes' WHERE id = %s",
            (chat,),
        )
        # The same real background sweep asks again after the visitor chose to wait.
        deadline = time.monotonic() + 25
        next_prompt = None
        while time.monotonic() < deadline:
            frame = json.loads(visitor.recv(timeout=max(0.1, deadline - time.monotonic())))
            if frame.get("type") == "ping":
                send(visitor, type="pong")
            if (
                frame.get("body")
                == "Our agents are all currently busy right now. Would you like to wait?"
            ):
                next_prompt = frame
                break
        assert next_prompt is not None and next_prompt["id"] > prompt["id"]
        send(visitor, type="handoff_wait_response", prompt_id=next_prompt["id"], choice="end")
        receive(visitor, "message", body="This chat was closed at your request.")
        receive(visitor, "state", state="closed")
        assert stack.feed(alex)["items"] == []
        assert stack.feed(alex)["unread_count"] == 0


def test_closed_callback_drops_pending_attention_push_before_worker_delivery(stack):
    alex, _ = staff(stack)
    callback_site()
    stack.subscribe(alex, "closed-wait")
    with stack.visitor("careers", "careers-key") as visitor, stack.agent(alex) as agent:
        chat = prechat(visitor)
        assert stack.feed(alex)["unread_count"] == 1
        send(agent, type="close_attention", conversation_id=chat)
        receive(agent, "state", state="closed")
    stack.start_worker()
    eventually(drained)
    assert stack.gateway.received() == []
    assert stack.feed(alex)["items"] == []
    assert sql("SELECT attempts FROM push_deliveries") == [(0,)]


def test_worker_restart_retries_real_https_then_removes_expired_device(stack):
    """Catches lost durable jobs, hot retries, broken crypto and a poisoned worker queue."""
    alex, _ = staff(stack)
    _, endpoint = stack.subscribe(alex, "retry")
    stack.gateway.respond("retry", 503, 201)
    assert (
        stack.http.post(
            "/api/notifications/push/test", headers=alex, json={"endpoint": endpoint}
        ).status_code
        == 202
    )
    worker = stack.start_worker()

    def first_attempt():
        rows = sql("SELECT attempts, finished_at, next_attempt_at > now() FROM push_deliveries")
        assert rows == [(1, None, True)]

    eventually(first_attempt)
    stack.stop_process(worker)
    assert len(stack.gateway.received(accepted=False)) == 1
    assert stack.gateway.received() == []
    sql("UPDATE push_deliveries SET next_attempt_at = now()")
    stack.start_worker()
    eventually(drained)
    assert sql("SELECT attempts FROM push_deliveries") == [(2,)]
    attempts = stack.gateway.received(accepted=False)
    assert [row["status"] for row in attempts] == [503, 201]
    assert attempts[0]["payload"]["notification_id"] == attempts[1]["payload"]["notification_id"]

    _, expired = stack.subscribe(alex, "expired")
    stack.gateway.respond("expired", 410)
    assert (
        stack.http.post(
            "/api/notifications/push/test", headers=alex, json={"endpoint": expired}
        ).status_code
        == 202
    )
    eventually(drained)
    assert sql("SELECT endpoint FROM push_subscriptions ORDER BY endpoint") == [(endpoint,)]
    assert (
        stack.http.post(
            "/api/notifications/push/test", headers=alex, json={"endpoint": expired}
        ).status_code
        == 404
    )
    assert (
        stack.http.post(
            "/api/notifications/push/test", headers=alex, json={"endpoint": endpoint}
        ).status_code
        == 202
    )
    eventually(drained)
    assert len(stack.gateway.received()) == 2


def test_two_workers_deliver_burst_once_per_device_with_correct_feed_pagination(stack):
    """Catches lost notifications or duplicate delivery under concurrent row claims."""
    alex, _ = staff(stack)
    insert_site("easy", "SampleSite", "easy-key")
    stack.subscribe(alex, "desktop")
    stack.subscribe(alex, "phone", silent=True)
    stack.start_worker()
    stack.start_worker()
    with stack.visitor("easy", "easy-key") as visitor, stack.agent(alex) as agent:
        chat = prechat(visitor)
        send(agent, type="join", conversation_id=chat)
        receive(agent, "state", state="human")
        for _ in range(36):
            client_id = str(uuid4())
            send(
                visitor, type="message", client_message_id=client_id, body="secret visitor message"
            )
            receive(visitor, "ack", client_message_id=client_id)
    eventually(drained, timeout=30)
    first = stack.feed(alex)
    assert first["unread_count"] == 36 and first["unread_conversations"] == {chat: 36}
    assert len(first["items"]) == 30
    second = stack.feed(alex, f"?cursor={first['next_cursor']}")
    assert len(second["items"]) == 6 and second["next_cursor"] is None
    ids = [item["id"] for item in first["items"] + second["items"]]
    assert len(set(ids)) == 36
    delivered = stack.gateway.received()
    assert len(delivered) == 72
    assert Counter(row["payload"]["notification_id"] for row in delivered) == dict.fromkeys(ids, 2)
    assert Counter(row["path"] for row in delivered) == {
        "/fcm/send/desktop": 36,
        "/fcm/send/phone": 36,
    }
    response = stack.http.post(
        "/api/notifications/read-all", headers=alex, json={"through_id": first["items"][0]["id"]}
    )
    assert response.status_code == 204
    assert stack.feed(alex, "?unread=true")["items"] == []
    assert stack.feed(alex)["unread_count"] == 0


@pytest.mark.parametrize(
    "block", ["read", "muted", "types", "inactive", "revoked", "unsubscribed", "stale"]
)
def test_pending_push_is_suppressed_when_it_no_longer_applies(stack, block):
    """Catches late alerts after a read, preference change, account revocation or expiry."""
    alex, _ = staff(stack)
    site = callback_site()
    _, endpoint = stack.subscribe(alex, "blocked")
    with stack.visitor("careers", "careers-key") as visitor:
        prechat(visitor)
    feed = stack.feed(alex)
    assert feed["unread_count"] == 1
    assert sql("SELECT count(*) FROM push_deliveries WHERE finished_at IS NULL") == [(1,)]
    if block == "read":
        assert (
            stack.http.post(
                f"/api/notifications/{feed['items'][0]['id']}/read", headers=alex
            ).status_code
            == 204
        )
    elif block == "muted":
        assert (
            stack.http.put(
                "/api/notifications/preferences/push",
                headers=alex,
                json={"site_id": str(site), "enabled": False, "scenarios": ["needs_attention"]},
            ).status_code
            == 200
        )
    elif block == "types":
        assert (
            stack.http.put(
                "/api/notifications/preferences/push",
                headers=alex,
                json={"site_id": str(site), "enabled": True, "scenarios": ["bot"]},
            ).status_code
            == 200
        )
    elif block == "inactive":
        sql("UPDATE users SET is_active = false WHERE email = %s", (ALEX_EMAIL,))
    elif block == "revoked":
        sql("UPDATE users SET token_version = token_version + 1 WHERE email = %s", (ALEX_EMAIL,))
    elif block == "unsubscribed":
        assert (
            stack.http.request(
                "DELETE",
                "/api/notifications/push/subscriptions",
                headers=alex,
                json={"endpoint": endpoint},
            ).status_code
            == 204
        )
    else:
        sql("UPDATE push_deliveries SET created_at = now() - interval '16 minutes'")
    stack.start_worker()
    eventually(drained)
    assert stack.gateway.received(accepted=False) == []
    assert sql("SELECT sum(attempts) FROM push_deliveries")[0][0] in (None, 0)


@pytest.mark.parametrize("status", [429, 503])
def test_persistent_push_failure_stops_retrying_without_blocking_other_devices(stack, status):
    """Catches infinite retries and starvation of another valid subscribed device."""
    alex, _ = staff(stack)
    _, failed = stack.subscribe(alex, "failing")
    _, healthy = stack.subscribe(alex, "healthy")
    stack.gateway.respond("failing", *([status] * 6))
    assert (
        stack.http.post(
            "/api/notifications/push/test", headers=alex, json={"endpoint": failed}
        ).status_code
        == 202
    )
    assert (
        stack.http.post(
            "/api/notifications/push/test", headers=alex, json={"endpoint": healthy}
        ).status_code
        == 202
    )
    stack.start_worker()
    for attempt in range(1, 6):

        def completed_attempt(expected_attempt=attempt):
            row = sql(
                "SELECT attempts, finished_at IS NOT NULL FROM push_deliveries JOIN push_subscriptions ON push_subscriptions.id = subscription_id WHERE endpoint = %s",
                (failed,),
            )[0]
            assert row == (expected_attempt, expected_attempt == 5)

        eventually(completed_attempt)
        if attempt < 5:
            sql(
                "UPDATE push_deliveries SET next_attempt_at = now() WHERE subscription_id IN (SELECT id FROM push_subscriptions WHERE endpoint = %s)",
                (failed,),
            )
    eventually(drained)
    delivered = stack.gateway.received(accepted=False)
    assert Counter((row["path"], row["status"]) for row in delivered) == {
        ("/fcm/send/failing", status): 5,
        ("/fcm/send/healthy", 201): 1,
    }
    assert sql("SELECT count(*) FROM push_subscriptions") == [(2,)]
