"""Oracle: useful site/chat/category/action content, without contact or transcript data."""

import asyncio
from uuid import UUID, uuid4

import pytest

from app.db import session_maker
from app.models.conversation import Conversation
from app.models.visitor import Visitor
from app.repositories.notification_repo import NotificationRepository
from tests.test_notifications import auth
from tests.test_push_notifications import RecordingSender, deliver, subscription
from tests.test_push_notifications import push_config as push_config
from tests.ws_helpers import insert_site

KINDS = ["needs_attention", "live", "visitor_message", "bot", "closed"]


async def emit_content(site, scenario, inquiry="portal"):
    async with session_maker()() as session:
        visitor = Visitor(
            site_id=site,
            resume_token_hash=uuid4().hex,
            name="Private visitor",
            email="private@example.com",
        )
        session.add(visitor)
        await session.flush()
        chat = Conversation(
            id=UUID("123abc00-0000-4000-8000-000000000001"),
            site_id=site,
            visitor_id=visitor.id,
            state="bot",
            inquiry_type=inquiry,
            page_title="Secret transcript",
            page_url="https://secret.example",
        )
        session.add(chat)
        await session.flush()
        await NotificationRepository(session).emit(chat, scenario, "content-example")
        await session.commit()


@pytest.mark.parametrize(
    "scenario,title,action",
    [
        (
            "needs_attention",
            "Needs attention",
            "A visitor requested specialist help. Open the inbox to help.",
        ),
        (
            "live",
            "Live chat started",
            "A specialist joined this conversation. Open it to follow along.",
        ),
        (
            "visitor_message",
            "New visitor reply",
            "A visitor replied to your chat. Open it to respond.",
        ),
        (
            "bot",
            "New bot conversation",
            "A visitor started or resumed an assistant conversation. Open it to follow along.",
        ),
        ("closed", "Chat closed", "This conversation has ended. Open it to review."),
    ],
)
def test_delivered_content_identifies_the_site_chat_category_and_next_action(
    client, scenario, title, action
):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "key")
    client.post("/api/notifications/push/subscriptions", headers=headers, json=subscription())
    client.put(
        "/api/notifications/preferences/push",
        headers=headers,
        json={"site_id": str(site), "enabled": True, "scenarios": KINDS},
    )
    client.portal.call(emit_content, site, scenario)
    sender = RecordingSender()
    assert client.portal.call(deliver, sender) is True
    content = sender.delivered[0]
    assert content["title"] == f"SampleSite · {title}"
    assert content["body"] == f"Chat #123ABC · Portal support\n{action}"
    assert content["action_label"] == "View chat"
    assert "Private visitor" not in str(content) and "private@example.com" not in str(content)
    assert "Secret transcript" not in str(content) and "secret.example" not in str(content)


def test_selected_preview_matches_delivered_test_without_creating_inbox_activity(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "key")
    device = subscription(silent=True)
    client.post("/api/notifications/push/subscriptions", headers=headers, json=device)
    before = client.get("/api/notifications", headers=headers).json()
    preview = client.get(
        "/api/notifications/push/preview",
        headers=headers,
        params={"site_id": str(site), "scenario": "bot"},
    )
    assert preview.status_code == 200
    assert preview.json() == {
        "title": "Preview: SampleSite · New bot conversation",
        "body": "Example chat #A1B2C3 · Portal support\nA visitor started or resumed an assistant conversation. Open it to follow along.",
        "action_label": "Open inbox",
    }
    response = client.post(
        "/api/notifications/push/test",
        headers=headers,
        json={"endpoint": device["endpoint"], "site_id": str(site), "scenario": "bot"},
    )
    assert response.status_code == 202
    sender = RecordingSender()
    client.portal.call(deliver, sender)
    sent = sender.delivered[0]
    assert {key: sent[key] for key in ("title", "body", "action_label")} == preview.json()
    assert sent["silent"] is True and sent["conversation_id"] is None
    assert client.get("/api/notifications", headers=headers).json() == before


def test_preview_validates_selection_and_authentication(client):
    assert client.get("/api/notifications/push/preview").status_code == 401
    _, headers = auth(client)
    assert (
        client.get(
            "/api/notifications/push/preview", headers=headers, params={"scenario": "email"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/notifications/push/preview", headers=headers, params={"site_id": str(uuid4())}
        ).status_code
        == 404
    )


def test_missing_inquiry_and_long_site_names_still_produce_a_readable_bounded_alert(client):
    _, headers = auth(client)
    site = insert_site("long", "Website " + "界" * 500, "key")
    client.post("/api/notifications/push/subscriptions", headers=headers, json=subscription())
    client.portal.call(emit_content, site, "visitor_message", None)
    sender = RecordingSender()
    client.portal.call(deliver, sender)
    content = sender.delivered[0]
    assert content["title"].startswith("Website ") and "… · New visitor reply" in content["title"]
    assert len(content["title"]) <= 200
    assert (
        content["body"]
        == "Chat #123ABC · General inquiry\nA visitor replied to your chat. Open it to respond."
    )


def test_pending_preview_uses_the_latest_selected_example_and_rejects_custom_content(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "key")
    endpoint = subscription()["endpoint"]
    client.post("/api/notifications/push/subscriptions", headers=headers, json=subscription())
    for kind in ("bot", "closed"):
        assert (
            client.post(
                "/api/notifications/push/test",
                headers=headers,
                json={"endpoint": endpoint, "site_id": str(site), "scenario": kind},
            ).status_code
            == 202
        )
    assert (
        client.post(
            "/api/notifications/push/test",
            headers=headers,
            json={"endpoint": endpoint, "title": "Untrusted text"},
        ).status_code
        == 422
    )
    sender = RecordingSender()
    assert client.portal.call(deliver, sender) is True
    assert client.portal.call(deliver, sender) is False
    assert sender.delivered[0]["title"] == "Preview: SampleSite · Chat closed"


async def send_during_delivery(user_id, endpoint):
    from sqlalchemy import text

    from app.repositories.push_repo import PushRepository

    entered, release = asyncio.Event(), asyncio.Event()

    class HeldSender(RecordingSender):
        async def send(self, device, payload):
            self.delivered.append(payload)
            entered.set()
            await release.wait()
            return 201

    sender = HeldSender()
    delivering = asyncio.create_task(deliver(sender))
    await asyncio.wait_for(entered.wait(), 5)

    async def request_again():
        async with session_maker()() as session:
            await PushRepository(session).test(
                user_id,
                endpoint,
                {
                    "title": "Selected preview",
                    "body": "Latest example",
                    "action_label": "Open inbox",
                },
            )
            await session.commit()

    saving = asyncio.create_task(request_again())

    async def wait_until_saving_is_blocked():
        async with session_maker()() as session:
            while not await session.scalar(
                text(
                    "SELECT count(*) FROM pg_locks WHERE NOT granted AND locktype = 'transactionid'"
                )
            ):
                await asyncio.sleep(0.01)

    try:
        await asyncio.wait_for(wait_until_saving_is_blocked(), 5)
    finally:
        release.set()
        await delivering
    await saving
    next_sender = RecordingSender()
    await deliver(next_sender)
    return sender.delivered + next_sender.delivered


def test_a_preview_requested_during_delivery_is_not_lost(client):
    user, headers = auth(client)
    device = subscription()
    client.post("/api/notifications/push/subscriptions", headers=headers, json=device)
    client.post(
        "/api/notifications/push/test", headers=headers, json={"endpoint": device["endpoint"]}
    )
    sent = client.portal.call(send_during_delivery, user, device["endpoint"])
    assert [item["title"] for item in sent] == [
        "SupportChat · Push notification test",
        "Selected preview",
    ]
