from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.db import session_maker
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.repositories.message_repo import MessageRepository
from app.security.passwords import hash_password
from app.services.conversation_service import ConversationService
from tests.bot_fixtures import insert_bot_conversation, seed_brand_articles
from tests.ws_helpers import ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD, conversation_state, message_count

IDLE_WARNING = "This chat will close in 1 minute. Send a message to keep active."
IDLE_CLOSED = "This chat has been closed automatically."
START = datetime(2026, 9, 10, 15, 0, tzinfo=UTC)
FOUR_MIN = timedelta(minutes=4)
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
        assert early is not None
        assert conversation_state(conversation_id) == "bot"
        assert message_count(conversation_id, body=IDLE_WARNING) == 1
        assert message_count(conversation_id, body=IDLE_CLOSED) == 0
        closed = await service.tick_idle(conversation_id, now=START + FIVE_MIN)

    assert closed is not None
    assert conversation_state(conversation_id) == "closed"
    assert message_count(conversation_id, body=IDLE_WARNING) == 1
    assert message_count(conversation_id, body=IDLE_CLOSED) == 1
    async with session_maker()() as session:
        loaded = await session.get(Conversation, conversation_id)
        assert loaded is not None
        assert loaded.closed_at == START + FIVE_MIN


async def test_handoff_waits_while_prechat_and_human_chats_close_on_the_idle_ttl(
    migrated_db,
) -> None:
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

    assert conversation_state(queued_id) == "queued"
    assert (
        message_count(
            queued_id, body="Our agents are all currently busy right now. Would you like to wait?"
        )
        == 1
    )
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
        assert still_open is not None
        assert conversation_state(conversation_id) == "bot"
        assert message_count(conversation_id, body=IDLE_CLOSED) == 0
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


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


async def _line(session, conversation_id, body: str) -> Message:
    message = await session.scalar(
        select(Message).where(Message.conversation_id == conversation_id, Message.body == body)
    )
    assert message is not None
    return message


async def test_idle_warning_at_four_minutes_does_not_extend_ttl(migrated_db) -> None:
    """Catches a warning system line bumping last_message_at and delaying the 5-minute close."""
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id = await _open_chat(session, easy)
        service = ConversationService(session)
        warned = await service.tick_idle(conversation_id, now=START + FOUR_MIN)
        loaded = await session.get(Conversation, conversation_id)
        assert loaded is not None
        assert warned is not None
        assert conversation_state(conversation_id) == "bot"
        assert message_count(conversation_id, body=IDLE_WARNING) == 1
        assert message_count(conversation_id, body=IDLE_CLOSED) == 0
        assert _aware(loaded.last_message_at) == START
        closed = await service.tick_idle(conversation_id, now=START + FIVE_MIN)

    assert closed is not None
    assert conversation_state(conversation_id) == "closed"
    assert message_count(conversation_id, body=IDLE_WARNING) == 1
    assert message_count(conversation_id, body=IDLE_CLOSED) == 1


async def test_idle_close_backfills_warning_one_minute_before_close(migrated_db) -> None:
    """Catches a 5-minute jump that closes without leaving the 1-minute warning in the transcript."""
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id = await _open_chat(session, easy)
        closed = await ConversationService(session).tick_idle(conversation_id, now=START + FIVE_MIN)
        warning = await _line(session, conversation_id, IDLE_WARNING)
        auto_close = await _line(session, conversation_id, IDLE_CLOSED)

    assert closed is not None
    assert conversation_state(conversation_id) == "closed"
    assert _aware(warning.created_at) == START + FOUR_MIN
    assert _aware(auto_close.created_at) == START + FIVE_MIN
    assert warning.id < auto_close.id


async def test_idle_close_pills_are_idempotent_across_ticks(migrated_db) -> None:
    """Catches a second sweep duplicating the warning or automatic-close system lines."""
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id = await _open_chat(session, easy)
        service = ConversationService(session)
        await service.tick_idle(conversation_id, now=START + FOUR_MIN)
        await service.tick_idle(conversation_id, now=START + FOUR_MIN)
        await service.tick_idle(conversation_id, now=START + FIVE_MIN)
        again = await service.tick_idle(
            conversation_id, now=START + FIVE_MIN + timedelta(minutes=1)
        )

    assert again is None
    assert conversation_state(conversation_id) == "closed"
    assert message_count(conversation_id, body=IDLE_WARNING) == 1
    assert message_count(conversation_id, body=IDLE_CLOSED) == 1


async def test_expired_sweep_persists_idle_pills_and_leaves_other_sites(migrated_db) -> None:
    """Catches a sweep that closes without transcript pills, or that also closes a fresh Sample Services chat."""
    async with session_maker()() as session:
        easy, bg, _timing, _fcra = await seed_brand_articles(session)
        stale_id = await _open_chat(session, easy, when=START)
        other_id = await _open_chat(session, bg, when=START + timedelta(minutes=4))
        closed = await ConversationService(session).close_expired(now=START + FIVE_MIN)

    assert {item.conversation.id for item in closed} == {stale_id}
    assert conversation_state(stale_id) == "closed"
    assert conversation_state(other_id) == "bot"
    assert message_count(stale_id, body=IDLE_WARNING) == 1
    assert message_count(stale_id, body=IDLE_CLOSED) == 1
    assert message_count(other_id, body=IDLE_WARNING) == 0
    assert message_count(other_id, body=IDLE_CLOSED) == 0


async def test_expired_sweep_warns_at_four_minutes_without_closing(migrated_db) -> None:
    """Catches a worker sweep that either skips the 4-minute warning or closes a minute early."""
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id = await _open_chat(session, easy)
        results = await ConversationService(session).close_expired(now=START + FOUR_MIN)

    assert {item.conversation.id for item in results} == {conversation_id}
    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, body=IDLE_WARNING) == 1
    assert message_count(conversation_id, body=IDLE_CLOSED) == 0


async def test_queued_handoff_prompts_instead_of_persisting_idle_close_pills(migrated_db) -> None:
    """A waiting visitor must choose to end their handoff."""
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id = await _open_chat(session, easy, state="queued")
        await ConversationService(session).tick_idle(conversation_id, now=START + FIVE_MIN)

    assert conversation_state(conversation_id) == "queued"
    assert message_count(conversation_id, body=IDLE_WARNING) == 0
    assert message_count(conversation_id, body=IDLE_CLOSED) == 0
    assert (
        message_count(
            conversation_id,
            body="Our agents are all currently busy right now. Would you like to wait?",
        )
        == 1
    )
