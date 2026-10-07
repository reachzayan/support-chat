"""Push contract: opt-in devices, private events, durable retries and account isolation."""

from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import select

from app.db import session_maker
from tests.test_notifications import auth, escalate, make_chat
from tests.ws_helpers import JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD, insert_site


def subscription(endpoint="https://fcm.googleapis.com/fcm/send/device-a", silent=False):
    public = (
        ec.derive_private_key(7, ec.SECP256R1())
        .public_key()
        .public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    )
    return {
        "endpoint": endpoint,
        "keys": {
            "p256dh": urlsafe_b64encode(public).decode().rstrip("="),
            "auth": urlsafe_b64encode(b"0123456789abcdef").decode().rstrip("="),
        },
        "silent": silent,
    }


@pytest.fixture(autouse=True)
def push_config(monkeypatch):
    monkeypatch.setenv(
        "PUSH_VAPID_PRIVATE_KEY", urlsafe_b64encode((3).to_bytes(32)).decode().rstrip("=")
    )
    monkeypatch.setenv("PUSH_VAPID_SUBJECT", "mailto:notifications@example.com")
    from app.settings import reset_settings_cache

    reset_settings_cache()


def test_push_requires_auth_and_returns_only_public_configuration(client, push_config):
    assert client.get("/api/notifications/push/config").status_code == 401
    _, headers = auth(client)
    result = client.get("/api/notifications/push/config", headers=headers)
    assert result.status_code == 200
    assert result.json()["configured"] is True
    assert set(result.json()) == {"configured", "public_key"}
    assert len(result.json()["public_key"]) == 87


def test_subscriptions_are_private_and_rebinding_cancels_previous_account_jobs(client, push_config):
    _, headers = auth(client)
    _, other = auth(client, JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD)
    payload = subscription()
    created = client.post("/api/notifications/push/subscriptions", headers=headers, json=payload)
    assert created.status_code == 200
    first_id = created.json()["id"]
    repeated = client.post("/api/notifications/push/subscriptions", headers=headers, json=payload)
    assert repeated.json()["id"] == first_id
    site = insert_site("easy", "SampleSite", "key")
    chat_id, visitor_id = client.portal.call(make_chat, site)
    client.portal.call(escalate, chat_id, visitor_id)
    second = client.post("/api/notifications/push/subscriptions", headers=other, json=payload)
    assert second.status_code == 200
    assert second.json()["id"] != first_id
    assert client.portal.call(pending_count) == 0
    client.request(
        "DELETE",
        "/api/notifications/push/subscriptions",
        headers=headers,
        json={"endpoint": payload["endpoint"]},
    )
    assert client.portal.call(subscription_count) == 1
    client.request(
        "DELETE",
        "/api/notifications/push/subscriptions",
        headers=other,
        json={"endpoint": payload["endpoint"]},
    )
    assert client.portal.call(subscription_count) == 0


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/send/a",
        "https://127.0.0.1/push",
        "https://fcm.googleapis.com.evil.test/push",
        "https://fcm.googleapis.com:8443/push",
        "https://user:password@fcm.googleapis.com/push",
    ],
)
def test_push_rejects_untrusted_endpoints(client, push_config, endpoint):
    _, headers = auth(client)
    response = client.post(
        "/api/notifications/push/subscriptions", headers=headers, json=subscription(endpoint)
    )
    assert response.status_code == 422
    assert client.portal.call(subscription_count) == 0


async def subscription_count():
    from app.models.push_subscription import PushSubscription

    async with session_maker()() as session:
        return len((await session.scalars(select(PushSubscription))).all())


async def pending_count():
    from app.models.push_subscription import PushDelivery

    async with session_maker()() as session:
        return len(
            (
                await session.scalars(
                    select(PushDelivery).where(PushDelivery.finished_at.is_(None))
                )
            ).all()
        )


class RecordingSender:
    def __init__(self, statuses=(201,)):
        self.statuses = iter(statuses)
        self.delivered = []

    async def send(self, device, payload):
        self.delivered.append(payload)
        return next(self.statuses)


async def deliver(sender, now=None):
    from app.workers.push_notifications import deliver_next

    async with session_maker()() as session:
        return await deliver_next(session, sender, now=now)


def test_events_queue_per_device_after_commit_without_duplicate_or_old_history(client, push_config):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "key")
    chat_id, visitor_id = client.portal.call(make_chat, site)
    client.portal.call(escalate, chat_id, visitor_id)
    client.post("/api/notifications/push/subscriptions", headers=headers, json=subscription())
    assert client.portal.call(pending_count) == 0
    second_chat, second_visitor = client.portal.call(make_chat, site)
    client.portal.call(escalate, second_chat, second_visitor)
    client.portal.call(escalate, second_chat, second_visitor)
    assert client.portal.call(pending_count) == 1
    sender = RecordingSender()
    assert client.portal.call(deliver, sender) is True
    assert client.portal.call(deliver, sender) is False
    assert len(sender.delivered) == 1
    item = sender.delivered[0]
    assert (item["title"], item["conversation_id"], item["silent"]) == (
        "SampleSite · Needs attention",
        str(second_chat),
        False,
    )
    assert item["body"].endswith(
        "General inquiry\nA visitor requested specialist help. Open the inbox to help."
    )
    assert "Ada" not in str(item) and "ada@example.com" not in str(item)


def test_read_events_and_muted_scenarios_are_not_delivered(client, push_config):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "key")
    client.post("/api/notifications/push/subscriptions", headers=headers, json=subscription())
    chat_id, visitor_id = client.portal.call(make_chat, site)
    client.portal.call(escalate, chat_id, visitor_id)
    item_id = client.get("/api/notifications", headers=headers).json()["items"][0]["id"]
    client.post(f"/api/notifications/{item_id}/read", headers=headers)
    sender = RecordingSender(())
    assert client.portal.call(deliver, sender) is True
    assert sender.delivered == []
    assert client.portal.call(pending_count) == 0
    client.put(
        "/api/notifications/preferences/push",
        headers=headers,
        json={"site_id": str(site), "enabled": False, "scenarios": ["needs_attention"]},
    )
    next_chat, next_visitor = client.portal.call(make_chat, site)
    client.portal.call(escalate, next_chat, next_visitor)
    assert client.portal.call(pending_count) == 0


def test_transient_failure_retries_and_expired_device_is_removed(client, push_config):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "key")
    client.post("/api/notifications/push/subscriptions", headers=headers, json=subscription())
    chat_id, visitor_id = client.portal.call(make_chat, site)
    client.portal.call(escalate, chat_id, visitor_id)
    sender = RecordingSender((503, 410))
    now = datetime.now(UTC)
    assert client.portal.call(deliver, sender, now) is True
    assert client.portal.call(pending_count) == 1
    assert client.portal.call(deliver, sender, now) is False
    assert client.portal.call(deliver, sender, now + timedelta(minutes=2)) is True
    assert client.portal.call(subscription_count) == 0
    assert client.portal.call(pending_count) == 0
