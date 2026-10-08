"""Notification contract: durable events, private read state, site/scenario preferences."""

from uuid import uuid4

from sqlalchemy import select

from app.db import session_maker
from app.models.conversation import Conversation
from app.models.visitor import Visitor
from app.services.conversation_service import ConversationService
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    JORDAN_EMAIL,
    JORDAN_NAME,
    JORDAN_PASSWORD,
    insert_site,
    insert_staff,
    login_staff,
)


def auth(client, email=ALEX_EMAIL, name=ALEX_NAME, password=ALEX_PASSWORD):
    user_id = insert_staff(email, name, password)
    token = login_staff(client, email, password)
    return user_id, {"Authorization": f"Bearer {token}"}


def test_notifications_require_staff(client):
    response = client.get("/api/notifications")
    assert response.status_code == 401


def test_preferences_are_per_user_site_and_scenario(client):
    _, headers = auth(client)
    _, other = auth(client, JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD)
    easy = str(insert_site("easy", "SampleSite", "easy-key"))
    bg = str(insert_site("background", "Sample Services", "bg-key"))
    result = client.put(
        "/api/notifications/preferences",
        headers=headers,
        json={
            "site_id": easy,
            "scenario": "needs_attention",
            "in_app": False,
        },
    )
    assert result.status_code == 200
    prefs = client.get("/api/notifications/preferences", headers=headers).json()["sites"]
    assert (
        next(row for row in prefs if row["site_id"] == easy)["scenarios"]["needs_attention"]
        is False
    )
    assert next(row for row in prefs if row["site_id"] == easy)["scenarios"]["live"] is True
    assert (
        next(row for row in prefs if row["site_id"] == bg)["scenarios"]["needs_attention"] is True
    )
    others = client.get("/api/notifications/preferences", headers=other).json()["sites"]
    assert (
        next(row for row in others if row["site_id"] == easy)["scenarios"]["needs_attention"]
        is True
    )
    assert (
        client.put(
            "/api/notifications/preferences",
            headers=headers,
            json={
                "site_id": str(uuid4()),
                "scenario": "live",
                "in_app": True,
            },
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/api/notifications/preferences",
            headers=headers,
            json={
                "site_id": easy,
                "scenario": "email",
                "in_app": True,
            },
        ).status_code
        == 422
    )


def test_empty_notification_feed(client):
    _, headers = auth(client)
    response = client.get("/api/notifications", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "unread_count": 0,
        "unread_conversations": {},
        "unread_conversation_context": {},
        "next_cursor": None,
        "latest_id": None,
    }


async def make_chat(site_id, state="bot"):
    async with session_maker()() as session:
        visitor = Visitor(
            site_id=site_id, resume_token_hash=uuid4().hex, name="Ada", email="ada@example.com"
        )
        session.add(visitor)
        await session.flush()
        chat = Conversation(site_id=site_id, visitor_id=visitor.id, state=state)
        session.add(chat)
        await session.commit()
        return chat.id, visitor.id


async def escalate(chat_id, visitor_id):
    from app.services.handoff_service import HandoffService, HandoffTrigger

    async with session_maker()() as session:
        await HandoffService(session).open_handoff(
            HandoffTrigger(
                conversation_id=chat_id,
                reason="visitor_request",
                original_question="Help",
            )
        )
        await session.commit()


def test_handoff_is_durable_deduplicated_and_read_state_is_private(client):
    _, headers = auth(client)
    _, other = auth(client, JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD)
    site_id = insert_site("easy", "SampleSite", "easy-key")
    chat_id, visitor_id = client.portal.call(make_chat, site_id)
    client.portal.call(escalate, chat_id, visitor_id)
    client.portal.call(escalate, chat_id, visitor_id)
    feed = client.get("/api/notifications", headers=headers).json()
    assert feed["unread_count"] == 1
    assert len(feed["items"]) == 1
    item = feed["items"][0]
    assert (item["conversation_id"], item["site_name"], item["scenario"], item["read_at"]) == (
        str(chat_id),
        "SampleSite",
        "needs_attention",
        None,
    )
    assert client.post(f"/api/notifications/{item['id']}/read", headers=other).status_code == 404
    assert client.post(f"/api/notifications/{item['id']}/read", headers=headers).status_code == 204
    assert client.get("/api/notifications?unread=true", headers=headers).json()["items"] == []
    assert client.get("/api/notifications", headers=other).json()["unread_count"] == 1
    assert (
        client.get("/api/notifications", headers=headers).json()["items"][0]["read_at"] is not None
    )


def test_disabled_scenario_does_not_suppress_another_site(client):
    _, headers = auth(client)
    easy = insert_site("easy", "SampleSite", "easy-key")
    bg = insert_site("background", "Sample Services", "bg-key")
    client.put(
        "/api/notifications/preferences",
        headers=headers,
        json={
            "site_id": str(easy),
            "scenario": "needs_attention",
            "in_app": False,
        },
    )
    for site in [easy, bg]:
        chat_id, visitor_id = client.portal.call(make_chat, site)
        client.portal.call(escalate, chat_id, visitor_id)
    feed = client.get("/api/notifications", headers=headers).json()
    assert feed["unread_count"] == 1
    assert [row["site_id"] for row in feed["items"]] == [str(bg)]


async def rolled_back_handoff(chat_id):
    from app.services.handoff_service import HandoffService, HandoffTrigger

    async with session_maker()() as session:
        await HandoffService(session).open_handoff(
            HandoffTrigger(
                conversation_id=chat_id,
                reason="visitor_request",
                original_question="Help",
            )
        )
        await session.rollback()
        return await session.scalar(select(Conversation.state).where(Conversation.id == chat_id))


def test_rolled_back_chat_event_never_delivers_a_notification(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "easy-key")
    chat_id, _ = client.portal.call(make_chat, site)
    assert client.portal.call(rolled_back_handoff, chat_id) == "bot"
    assert client.get("/api/notifications", headers=headers).json()["unread_count"] == 0


async def live_commands(chat_id, visitor_id, agent_id):
    from app.models.user import User

    async with session_maker()() as session:
        service = ConversationService(session)
        agent = await session.get(User, agent_id)
        await service.join(chat_id, agent)
        message_id = uuid4()
        await service.visitor_message(
            chat_id, visitor_id, "http://localhost:3000", message_id, "Hello"
        )
        await service.visitor_message(
            chat_id, visitor_id, "http://localhost:3000", message_id, "Hello"
        )


async def end_chat(chat_id, agent_id):
    from app.models.user import User

    async with session_maker()() as session:
        await ConversationService(session).end(chat_id, await session.get(User, agent_id))


async def durable_scenarios(chat_id):
    from app.models.notification import Notification

    async with session_maker()() as session:
        return list(
            await session.scalars(
                select(Notification.scenario)
                .where(Notification.conversation_id == chat_id)
                .order_by(Notification.id.desc())
            )
        )


def test_live_messages_notify_assignee_once_and_hide_own_actions(client):
    alex, headers = auth(client)
    _, other = auth(client, JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD)
    site = insert_site("easy", "SampleSite", "easy-key")
    client.put(
        "/api/notifications/preferences",
        headers=other,
        json={
            "site_id": str(site),
            "scenario": "closed",
            "in_app": True,
        },
    )
    chat_id, visitor_id = client.portal.call(make_chat, site)
    client.portal.call(live_commands, chat_id, visitor_id, alex)
    mine = client.get("/api/notifications", headers=headers).json()
    theirs = client.get("/api/notifications", headers=other).json()
    assert [row["scenario"] for row in mine["items"]] == ["visitor_message"]
    assert [row["scenario"] for row in theirs["items"]] == ["live"]
    through_id = theirs["items"][0]["id"]
    client.post("/api/notifications/read-all", headers=other, json={"through_id": through_id})
    assert client.get("/api/notifications", headers=other).json()["unread_count"] == 0
    assert client.get("/api/notifications", headers=headers).json()["unread_count"] == 1
    client.portal.call(end_chat, chat_id, alex)
    assert client.get("/api/notifications", headers=headers).json()["unread_count"] == 0
    assert client.get("/api/notifications", headers=other).json()["items"] == []


async def start_and_expire(chat_id, visitor_id):
    from datetime import UTC, datetime, timedelta

    async with session_maker()() as session:
        service = ConversationService(session)
        submission_id = uuid4()
        args = (
            chat_id,
            visitor_id,
            "http://localhost:3000",
            submission_id,
            "Ada",
            "ada@example.com",
            "",
            "other",
            "",
        )
        await service.submit_prechat(*args)
        await service.submit_prechat(*args)
        await service.tick_idle(chat_id, now=datetime.now(UTC) + timedelta(minutes=6))


def test_bot_start_and_automatic_close_respect_opt_in(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "easy-key")
    for scenario in ["bot", "closed"]:
        client.put(
            "/api/notifications/preferences",
            headers=headers,
            json={
                "site_id": str(site),
                "scenario": scenario,
                "in_app": True,
            },
        )
    chat_id, visitor_id = client.portal.call(make_chat, site, "prechat")
    client.portal.call(start_and_expire, chat_id, visitor_id)
    feed = client.get("/api/notifications", headers=headers).json()
    assert feed["items"] == []
    assert client.portal.call(durable_scenarios, chat_id) == ["closed", "bot"]


async def resume_chat(chat_id, visitor_id):
    from app.services.conversation_input import hash_resume_token

    async with session_maker()() as session:
        visitor = await session.get(Visitor, visitor_id)
        token = uuid4().hex
        visitor.resume_token_hash = hash_resume_token(token)
        await session.commit()
        service = ConversationService(session)
        await service.bootstrap(
            "easy",
            "easy-key",
            "http://localhost:3000",
            token,
            None,
            None,
            action="open",
            conversation_id=chat_id,
        )


async def resume_and_expire(chat_id, visitor_id):
    from datetime import UTC, datetime, timedelta

    await resume_chat(chat_id, visitor_id)
    async with session_maker()() as session:
        service = ConversationService(session)
        moment = datetime.now(UTC) + timedelta(minutes=6)
        await service.tick_idle(chat_id, now=moment)
        await service.tick_idle(chat_id, now=moment + timedelta(minutes=1))


def test_resumed_chat_notifies_each_close_once(client):
    """Two completed chat sessions produce two alerts; repeated idle ticks add none."""
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "easy-key")
    client.put(
        "/api/notifications/preferences",
        headers=headers,
        json={"site_id": str(site), "scenario": "closed", "in_app": True},
    )
    chat_id, visitor_id = client.portal.call(make_chat, site, "prechat")
    client.portal.call(start_and_expire, chat_id, visitor_id)
    client.portal.call(resume_and_expire, chat_id, visitor_id)
    feed = client.get("/api/notifications", headers=headers).json()
    assert feed["items"] == []
    assert client.portal.call(durable_scenarios, chat_id) == ["closed", "closed"]


async def emit_batch(chat_id, size=32):
    from app.repositories.notification_repo import NotificationRepository

    async with session_maker()() as session:
        chat = await session.get(Conversation, chat_id)
        repo = NotificationRepository(session)
        for index in range(size):
            await repo.emit(chat, "needs_attention", f"event:{chat_id}:{index}")
        await repo.emit(chat, "needs_attention", f"event:{chat_id}:0")
        await session.commit()


def test_feed_paginates_without_duplicates_and_read_all_leaves_new_events_unread(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "easy-key")
    chat, _ = client.portal.call(make_chat, site)
    client.portal.call(emit_batch, chat)
    first = client.get("/api/notifications", headers=headers).json()
    assert first["unread_count"] == 32
    assert len(first["items"]) == 30
    second = client.get(f"/api/notifications?cursor={first['next_cursor']}", headers=headers).json()
    assert len(second["items"]) == 2
    assert second["next_cursor"] is None
    assert not {row["id"] for row in first["items"]} & {row["id"] for row in second["items"]}
    client.portal.call(emit_batch, chat, 33)
    client.post(
        "/api/notifications/read-all", headers=headers, json={"through_id": first["items"][0]["id"]}
    )
    unread = client.get("/api/notifications?unread=true", headers=headers).json()
    assert unread["unread_count"] == 1
    assert len(unread["items"]) == 1


def test_unread_context_uses_current_state_and_includes_chats_outside_the_feed_page(client):
    alex, headers = auth(client)
    easy = insert_site("easy", "SampleSite", "easy-key")
    bg = insert_site("background", "Sample Services", "bg-key")
    queued, _ = client.portal.call(make_chat, easy, "queued")
    live, _ = client.portal.call(make_chat, bg)
    client.portal.call(emit_batch, queued, 1)
    client.portal.call(emit_batch, live, 32)

    async def join():
        from app.models.user import User

        async with session_maker()() as session:
            await ConversationService(session).join(live, await session.get(User, alex))

    client.portal.call(join)
    feed = client.get("/api/notifications", headers=headers).json()
    assert {row["conversation_id"] for row in feed["items"]} == {str(live)}
    assert feed["unread_conversation_context"] == {
        str(queued): {"site_id": str(easy), "state": "queued"},
        str(live): {"site_id": str(bg), "state": "human"},
    }
    assert feed["unread_conversations"] == {str(queued): 1, str(live): 32}


async def close_callback(chat_id, user_id):
    from app.models.user import User

    async with session_maker()() as session:
        chat = await session.get(Conversation, chat_id)
        chat.attention_needed = True
        await session.commit()
        user = await session.get(User, user_id)
        await ConversationService(session).close_attention(chat_id, user)


def test_callback_completion_notifies_other_staff_who_opted_in(client):
    alex, _ = auth(client)
    _, other = auth(client, JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD)
    site = insert_site("easy", "SampleSite", "easy-key")
    client.put(
        "/api/notifications/preferences",
        headers=other,
        json={
            "site_id": str(site),
            "scenario": "closed",
            "in_app": True,
        },
    )
    chat, _ = client.portal.call(make_chat, site, "queued")
    client.portal.call(close_callback, chat, alex)
    assert [
        row["scenario"] for row in client.get("/api/notifications", headers=other).json()["items"]
    ] == []
    assert client.portal.call(durable_scenarios, chat) == ["closed"]


def test_opening_a_chat_reads_its_entire_history_only_for_current_staff(client):
    _, headers = auth(client)
    _, other = auth(client, JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD)
    site = insert_site("easy", "SampleSite", "easy-key")
    chat_a, _ = client.portal.call(make_chat, site)
    chat_b, _ = client.portal.call(make_chat, site)
    client.portal.call(emit_batch, chat_a, 32)
    client.portal.call(emit_batch, chat_b, 1)
    first = client.get("/api/notifications", headers=headers).json()
    assert first["unread_conversations"] == {str(chat_a): 32, str(chat_b): 1}
    response = client.post(
        f"/api/notifications/conversations/{chat_a}/read",
        headers=headers,
        json={"through_id": first["items"][0]["id"]},
    )
    assert response.status_code == 204
    unread = client.get("/api/notifications?unread=true", headers=headers).json()
    assert unread["unread_count"] == 1
    assert unread["unread_conversations"] == {str(chat_b): 1}
    assert [row["conversation_id"] for row in unread["items"]] == [str(chat_b)]
    assert client.get("/api/notifications", headers=other).json()["unread_count"] == 33
    client.portal.call(emit_batch, chat_a, 33)
    client.post(
        f"/api/notifications/conversations/{chat_a}/read",
        headers=headers,
        json={"through_id": first["items"][0]["id"]},
    )
    assert client.get("/api/notifications", headers=headers).json()["unread_count"] == 2


async def expire_chat(chat_id):
    from datetime import UTC, datetime, timedelta

    async with session_maker()() as session:
        chat = await session.get(Conversation, chat_id)
        chat.last_message_at = datetime.now(UTC) - timedelta(minutes=6)
        chat.prechat_submission_id = chat.prechat_submission_id or uuid4()
        chat.prechat_payload_hash = chat.prechat_payload_hash or "test-completed-prechat"
        await session.commit()
        await ConversationService(session).tick_idle(chat_id)


def test_automatic_close_removes_chat_alerts_for_all_staff_and_leaves_open_chats(client):
    _, headers = auth(client)
    _, other = auth(client, JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD)
    site = insert_site("easy", "SampleSite", "easy-key")
    expired, _ = client.portal.call(make_chat, site)
    active, _ = client.portal.call(make_chat, site)
    client.portal.call(emit_batch, expired, 32)
    client.portal.call(emit_batch, active, 1)
    assert client.get("/api/notifications", headers=headers).json()["unread_count"] == 33
    client.portal.call(expire_chat, expired)
    for credentials in (headers, other):
        feed = client.get("/api/notifications", headers=credentials).json()
        assert feed["unread_count"] == 1
        assert feed["unread_conversations"] == {str(active): 1}
        assert [row["conversation_id"] for row in feed["items"]] == [str(active)]


def test_closed_chat_never_reenters_feed_when_resumed(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "easy-key")
    client.put(
        "/api/notifications/preferences",
        headers=headers,
        json={"site_id": str(site), "scenario": "closed", "in_app": True},
    )
    chat, visitor = client.portal.call(make_chat, site)
    client.portal.call(emit_batch, chat, 1)
    client.portal.call(expire_chat, chat)
    client.portal.call(resume_chat, chat, visitor)
    feed = client.get("/api/notifications", headers=headers).json()
    assert feed["items"] == []
    assert feed["unread_count"] == 0
