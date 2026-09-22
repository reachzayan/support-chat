from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db import session_maker
from app.models.conversation import Conversation
from app.models.user import User
from app.repositories.message_repo import MessageRepository
from app.security.passwords import hash_password
from app.services.conversation_service import ConversationService
from tests.bot_fixtures import insert_bot_conversation, seed_brand_articles
from tests.ws_helpers import ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD, conversation_state, message_count

NUDGE = "Are you still there? Reply within a minute to keep this chat open."
START = datetime(2026, 9, 10, 15, 0, tzinfo=UTC)
FIVE_MIN = timedelta(minutes=5)


async def _open_chat(
    session,
    site,
    *,
    state: str = "bot",
    when: datetime = START,
    agent: User | None = None,
):
    _visitor, conversation = await insert_bot_conversation(session, site)
    await MessageRepository(session).create(
        conversation.id,
        conversation.site_id,
        "visitor",
        "how fast are results",
        client_message_id=uuid4(),
    )
    conversation.last_message_at = when
    conversation.state = state
    if agent is not None:
        conversation.assigned_agent_id = agent.id
    await session.commit()
    return conversation.id


async def test_chat_stays_open_until_five_minutes_then_closes(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id = await _open_chat(session, easy)
        service = ConversationService(session)
        early = await service.tick_idle(
            conversation_id, now=START + FIVE_MIN - timedelta(seconds=1)
        )
        assert early is None
        assert conversation_state(conversation_id) == "bot"
        closed = await service.tick_idle(conversation_id, now=START + FIVE_MIN)

    assert closed is not None
    assert conversation_state(conversation_id) == "closed"
    assert message_count(conversation_id, body=NUDGE) == 0
    async with session_maker()() as session:
        loaded = await session.get(Conversation, conversation_id)
        assert loaded is not None
        assert loaded.closed_at == START + FIVE_MIN


async def test_queued_and_human_chats_close_on_the_same_ttl(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        queued_id = await _open_chat(session, easy, state="queued")
        prechat_id = await _open_chat(session, easy, state="prechat")
        agent = User(
            email=ALEX_EMAIL,
            display_name=ALEX_NAME,
            password_hash=hash_password(ALEX_PASSWORD),
            is_admin=False,
            is_active=True,
        )
        session.add(agent)
        await session.commit()
        human_id = await _open_chat(session, easy, state="human", agent=agent)
        service = ConversationService(session)
        await service.tick_idle(queued_id, now=START + FIVE_MIN)
        await service.tick_idle(prechat_id, now=START + FIVE_MIN)
        await service.tick_idle(human_id, now=START + FIVE_MIN)

    assert conversation_state(queued_id) == "closed"
    assert conversation_state(prechat_id) == "closed"
    assert conversation_state(human_id) == "closed"


async def test_any_role_resets_the_five_minute_clock(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id = await _open_chat(session, easy)
        service = ConversationService(session)
        loaded_for_site = await session.get(Conversation, conversation_id)
        assert loaded_for_site is not None
        await MessageRepository(session).create(
            conversation_id,
            loaded_for_site.site_id,
            "system",
            "A specialist will join this chat shortly.",
        )
        loaded = await session.get(Conversation, conversation_id)
        assert loaded is not None
        loaded.last_message_at = START + timedelta(minutes=2)
        await session.commit()
        still_open = await service.tick_idle(
            conversation_id, now=START + timedelta(minutes=2) + FIVE_MIN - timedelta(seconds=1)
        )
        assert still_open is None
        assert conversation_state(conversation_id) == "bot"
        closed = await service.tick_idle(
            conversation_id, now=START + timedelta(minutes=2) + FIVE_MIN
        )

    assert closed is not None
    assert conversation_state(conversation_id) == "closed"


async def test_expired_sweep_closes_stale_chats_and_leaves_fresh_ones(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        stale_id = await _open_chat(session, easy, when=START)
        fresh_id = await _open_chat(session, easy, when=START + timedelta(minutes=4))
        closed_id = await _open_chat(session, easy, when=START)
        already = await session.get(Conversation, closed_id)
        assert already is not None
        already.state = "closed"
        already.closed_at = START
        await session.commit()
        closed = await ConversationService(session).close_expired(now=START + FIVE_MIN)

    assert {item.conversation.id for item in closed} == {stale_id}
    assert conversation_state(stale_id) == "closed"
    assert conversation_state(fresh_id) == "bot"
    assert conversation_state(closed_id) == "closed"


async def _open_prechat_form(
    session,
    site,
    *,
    when: datetime = START,
    with_visitor_message: bool = False,
):
    _visitor, conversation = await insert_bot_conversation(session, site)
    conversation.state = "prechat"
    conversation.last_message_at = when
    if with_visitor_message:
        await MessageRepository(session).create(
            conversation.id,
            conversation.site_id,
            "visitor",
            "how fast are results",
            client_message_id=uuid4(),
        )
    await session.commit()
    return conversation.id


async def test_prechat_form_without_visitor_messages_is_not_idle_due(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id = await _open_prechat_form(session, easy)
        service = ConversationService(session)
        conversation = await session.get(Conversation, conversation_id)
        assert conversation is not None
        due = await service._idle_due(conversation, START + FIVE_MIN)

    assert due is False
    assert conversation_state(conversation_id) == "prechat"


async def test_prechat_with_visitor_message_is_idle_due_past_ttl(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id = await _open_prechat_form(session, easy, with_visitor_message=True)
        service = ConversationService(session)
        conversation = await session.get(Conversation, conversation_id)
        assert conversation is not None
        due = await service._idle_due(conversation, START + FIVE_MIN)

    assert due is True


async def test_close_expired_skips_preform_prechat(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        form_id = await _open_prechat_form(session, easy)
        stale_chat_id = await _open_chat(session, easy, when=START)
        closed = await ConversationService(session).close_expired(now=START + FIVE_MIN)

    assert {item.conversation.id for item in closed} == {stale_chat_id}
    assert conversation_state(form_id) == "prechat"
    assert conversation_state(stale_chat_id) == "closed"
