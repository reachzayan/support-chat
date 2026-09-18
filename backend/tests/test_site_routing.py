import uuid

import pytest
from fastapi.testclient import TestClient

from app.chat.outcome_copy import CALLBACK_LINE
from app.db import session_maker
from app.models.user import User
from app.security.passwords import hash_password
from app.services.conversation_service import (
    CommandError,
    ConversationService,
)
from tests.bot_fixtures import (
    ADA_EMAIL,
    ADA_NAME,
    FALLBACK,
    WAITING_LINE,
    RecordingResponder,
    insert_bot_conversation,
    insert_site,
    seed_brand_articles,
)
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    HOST_ORIGIN,
    conversation_state,
    login_staff,
    message_count,
)

ADMIN_EMAIL = "admin@example.local"
ADMIN_PASSWORD = "secret"


class RaisingEmbedder:
    embedder_id = "fake:raise"
    dim = 1536

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("embed_documents must not run")

    async def embed_query(self, text: str) -> list[float] | None:
        raise AssertionError("embed_query must not run")


class RaisingResponder:
    async def generate(self, site, visitor_text, hits):
        raise AssertionError("Claude must not run")


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _insert_admin() -> uuid.UUID:
    from tests.ws_helpers import sync_session

    session = next(sync_session())
    try:
        user = User(
            email=ADMIN_EMAIL,
            display_name="Riley Chen",
            password_hash=hash_password(ADMIN_PASSWORD),
            is_admin=True,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id
    finally:
        session.close()


async def test_bot_off_prechat_is_callback_without_embed_or_claude(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        site.bot_enabled = False
        site.human_enabled = False
        visitor, conversation = await insert_bot_conversation(session, site)
        conversation.state = "prechat"
        await session.commit()
        service = ConversationService(
            session, responder=RaisingResponder(), embedder=RaisingEmbedder()
        )
        result = await service.submit_prechat(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            ADA_NAME,
            ADA_EMAIL,
            "",
            "sales",
            "Need a callback",
        )
        conversation_id = conversation.id

    assert result.generation_id is None
    assert conversation_state(conversation_id) == "queued"
    assert message_count(conversation_id, role="bot") == 0
    assert message_count(conversation_id, role="system", body=CALLBACK_LINE) == 1
    async with session_maker()() as session:
        loaded = await ConversationService(session)._conversations.get_by_id(conversation_id)
        assert loaded is not None
        assert loaded.attention_needed is True


async def test_join_forbidden_when_human_off(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        site.bot_enabled = False
        site.human_enabled = False
        _visitor, conversation = await insert_bot_conversation(session, site)
        conversation.state = "queued"
        conversation.attention_needed = True
        alex = User(
            email=ALEX_EMAIL,
            display_name=ALEX_NAME,
            password_hash=hash_password(ALEX_PASSWORD),
            is_admin=False,
            is_active=True,
        )
        session.add(alex)
        await session.commit()
        with pytest.raises(CommandError) as caught:
            await ConversationService(session).join(conversation.id, alex)
        assert caught.value.code == "join_disabled"
        await session.refresh(conversation)
        assert conversation.assigned_agent_id is None


async def test_bot_on_human_off_scope_clarification_does_not_create_callback(
    migrated_db,
) -> None:
    responder = RecordingResponder(answer="")
    async with session_maker()() as session:
        _easy, bg, _timing, _fcra = await seed_brand_articles(session)
        bg.human_enabled = False
        visitor, conversation = await insert_bot_conversation(session, bg)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        service = ConversationService(session, responder=responder)
        first = await service.visitor_message(
            conversation_id,
            visitor_id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "what is your unpublished internal pricing matrix",
        )
        if first.generation_id is not None:
            await service.run_bot_turn(conversation_id, first.generation_id)
        assert conversation_state(conversation_id) == "bot"
        assert message_count(conversation_id, role="bot") == 1
        assert message_count(conversation_id, role="system", body=FALLBACK) == 0
        assert message_count(conversation_id, role="system", body=CALLBACK_LINE) == 0
        yes = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), "yes"
        )
        if yes.generation_id is not None:
            await service.run_bot_turn(conversation_id, yes.generation_id)

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="bot") >= 1
    assert message_count(conversation_id, role="system", body=CALLBACK_LINE) == 0
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0


async def test_specialist_request_stays_bot_when_human_on(migrated_db) -> None:
    responder = RecordingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        service = ConversationService(session, responder=responder, embedder=RaisingEmbedder())
        result = await service.visitor_message(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "I want a specialist",
        )
        conversation_id = conversation.id

    assert result.generation_id is None
    assert conversation_state(conversation_id) == "queued"
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 1
    assert message_count(conversation_id, role="system", body=CALLBACK_LINE) == 0


async def test_ssn_never_embeds(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        service = ConversationService(
            session, responder=RaisingResponder(), embedder=RaisingEmbedder()
        )
        result = await service.visitor_message(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "My SSN is 123-45-6789",
        )
        conversation_id = conversation.id
    assert result.generation_id is None
    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=FALLBACK) == 1


async def test_patch_human_on_while_bot_off_is_422(client: TestClient) -> None:
    _insert_admin()
    token = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    created = client.post(
        "/api/sites",
        headers=_auth(token),
        json={
            "key": "samplesite",
            "name": "SampleSite",
            "greeting": "Talk to a specialist about screening.",
            "privacy_url": "https://sample-site.example.com/privacy",
        },
    )
    site_id = created.json()["id"]
    off = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(token),
        json={"bot_enabled": False, "human_enabled": False},
    )
    assert off.status_code == 200
    assert off.json()["bot_enabled"] is False
    assert off.json()["human_enabled"] is False
    illegal = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(token),
        json={"bot_enabled": False, "human_enabled": True},
    )
    assert illegal.status_code == 422
    listed = client.get("/api/sites", headers=_auth(token))
    row = listed.json()["items"][0]
    assert row["bot_enabled"] is False
    assert row["human_enabled"] is False


async def test_close_attention_closes_callback_without_join(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        site.bot_enabled = False
        site.human_enabled = False
        _visitor, conversation = await insert_bot_conversation(session, site)
        conversation.state = "queued"
        conversation.attention_needed = True
        alex = User(
            email=ALEX_EMAIL,
            display_name=ALEX_NAME,
            password_hash=hash_password(ALEX_PASSWORD),
            is_admin=False,
            is_active=True,
        )
        session.add(alex)
        await session.commit()
        result = await ConversationService(session).close_attention(conversation.id, alex)
        assert result.conversation.state == "closed"
        assert conversation_state(conversation.id) == "closed"


async def test_close_attention_rejected_on_live_queue(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        _visitor, conversation = await insert_bot_conversation(session, site)
        conversation.state = "queued"
        conversation.attention_needed = False
        alex = User(
            email=ALEX_EMAIL,
            display_name=ALEX_NAME,
            password_hash=hash_password(ALEX_PASSWORD),
            is_admin=False,
            is_active=True,
        )
        session.add(alex)
        await session.commit()
        with pytest.raises(CommandError):
            await ConversationService(session).close_attention(conversation.id, alex)
        assert conversation_state(conversation.id) == "queued"
