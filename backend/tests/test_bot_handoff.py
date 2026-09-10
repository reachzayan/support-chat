import asyncio
import uuid

import pytest

from app.db import session_maker
from app.models.conversation import Conversation
from app.models.user import User
from app.security.passwords import hash_password
from app.services.conversation_service import CommandError, ConversationService
from tests.bot_fixtures import (
    FALLBACK,
    FAST_QUERY,
    SCRIPTED_ANSWER,
    RecordingResponder,
    insert_bot_conversation,
    seed_brand_articles,
)
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    HOST_ORIGIN,
    JOIN_LINE_ALEX,
    conversation_state,
    message_count,
)


async def test_join_during_in_flight_generation_discards_answer(
    migrated_db,
) -> None:
    barrier = asyncio.Event()
    responder = RecordingResponder(answer=SCRIPTED_ANSWER, barrier=barrier)
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        alex = User(
            email=ALEX_EMAIL,
            display_name=ALEX_NAME,
            password_hash=hash_password(ALEX_PASSWORD),
            is_admin=False,
            is_active=True,
        )
        session.add(alex)
        await session.commit()
        service = ConversationService(session, responder=responder)
        result = await service.visitor_message(
            conversation.id, visitor.id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        conversation_id = conversation.id
        alex_id = alex.id
        generation_id = result.generation_id
    assert generation_id is not None
    assert conversation_state(conversation_id) == "bot"

    async with session_maker()() as bot_session:
        bot_task = asyncio.create_task(
            ConversationService(bot_session, responder=responder).run_bot_turn(
                conversation_id, generation_id
            )
        )
        await asyncio.sleep(0.05)
        async with session_maker()() as join_session:
            agent = await join_session.get(User, alex_id)
            assert agent is not None
            await ConversationService(join_session).join(conversation_id, agent)
        barrier.set()
        await bot_task

    assert conversation_state(conversation_id) == "human"
    assert message_count(conversation_id, role="bot") == 0
    assert message_count(conversation_id, role="system", body=FALLBACK) == 0
    assert message_count(conversation_id, role="system", body=JOIN_LINE_ALEX) == 1
    assert message_count(conversation_id, role="system", body=SCRIPTED_ANSWER) == 0


async def test_disable_selected_source_before_release_stores_generated_literal_zero_times(
    migrated_db,
) -> None:
    barrier = asyncio.Event()
    responder = RecordingResponder(answer=SCRIPTED_ANSWER, barrier=barrier)
    async with session_maker()() as session:
        easy, _bg, timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        responder.selected_ids = [timing.chunk_id]
        service = ConversationService(session, responder=responder)
        result = await service.visitor_message(
            conversation.id, visitor.id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        conversation_id = conversation.id
        page_id = timing.page_id
        generation_id = result.generation_id
    assert generation_id is not None

    async with session_maker()() as bot_session:
        bot_task = asyncio.create_task(
            ConversationService(bot_session, responder=responder).run_bot_turn(
                conversation_id, generation_id
            )
        )
        await asyncio.sleep(0.05)
        async with session_maker()() as disable_session:
            from app.models.kb_page import KbPage

            page = await disable_session.get(KbPage, page_id)
            assert page is not None
            page.enabled = False
            await disable_session.commit()
        barrier.set()
        await bot_task

    assert message_count(conversation_id, body=SCRIPTED_ANSWER) == 0
    assert message_count(conversation_id, role="bot") == 0
    assert message_count(conversation_id, role="system", body=FALLBACK) == 1


async def test_repeat_visitor_client_id_creates_one_row_and_at_most_one_provider_call(
    migrated_db,
) -> None:
    responder = RecordingResponder(answer=SCRIPTED_ANSWER)
    client_id = uuid.uuid4()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        service = ConversationService(session, responder=responder)
        first = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, client_id, FAST_QUERY
        )
        await service.run_bot_turn(conversation_id, first.generation_id)
        second = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, client_id, FAST_QUERY
        )
        if second.generation_id is not None:
            await service.run_bot_turn(conversation_id, second.generation_id)

    assert second.duplicate is True
    assert message_count(conversation_id, role="visitor", body=FAST_QUERY) == 1
    assert message_count(conversation_id, role="bot", body=SCRIPTED_ANSWER) == 1
    assert len(responder.calls) == 1


STILL_WAITING = "what is the turnaround time"


class ExplodingResponder:
    async def generate(self, site, visitor_text, articles):
        raise RuntimeError("provider down")


async def test_provider_crash_clears_generation_and_accepts_the_next_visitor_message(
    migrated_db,
) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        first = await ConversationService(session, responder=ExplodingResponder()).visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        assert first.generation_id is not None
        generation_id = first.generation_id

    async with session_maker()() as session:
        try:
            await ConversationService(session, responder=ExplodingResponder()).run_bot_turn(
                conversation_id, generation_id
            )
        except RuntimeError:
            pass

    async with session_maker()() as session:
        second = await ConversationService(session, responder=ExplodingResponder()).visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), STILL_WAITING
        )

    assert second.message is not None
    assert second.message.body == STILL_WAITING
    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=FALLBACK) == 1


async def test_latest_visitor_body_is_the_second_visitor_row(migrated_db) -> None:
    from app.repositories.message_repo import MessageRepository

    async with session_maker()() as session:
        easy, _bg, timing, _fcra = await seed_brand_articles(session)
        _visitor, conversation = await insert_bot_conversation(session, easy)
        messages = MessageRepository(session)
        await messages.create(
            conversation.id, "visitor", "first question", client_message_id=uuid.uuid4()
        )
        await messages.create(
            conversation.id, "bot", SCRIPTED_ANSWER, source_article_ids=[timing.id]
        )
        await messages.create(
            conversation.id, "visitor", FAST_QUERY, client_message_id=uuid.uuid4()
        )
        await session.commit()
        body = await messages.latest_visitor_body(conversation.id)
    assert body == FAST_QUERY


ASSISTANT_LINE = "You're now chatting with the assistant."


async def test_assigned_agent_can_return_chat_to_the_assistant(migrated_db) -> None:
    responder = RecordingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        alex = User(
            email=ALEX_EMAIL,
            display_name=ALEX_NAME,
            password_hash=hash_password(ALEX_PASSWORD),
            is_admin=False,
            is_active=True,
        )
        session.add(alex)
        await session.commit()
        service = ConversationService(session, responder=responder)
        await service.join(conversation.id, alex)
        await service.transfer_to_bot(conversation.id, alex)
        conversation_id = conversation.id
        visitor_id = visitor.id
    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=ASSISTANT_LINE) == 1

    async with session_maker()() as session:
        conversation = await session.get(Conversation, conversation_id)
        assert conversation is not None
        assert conversation.assigned_agent_id is None
        result = await ConversationService(session, responder=responder).visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        generation_id = result.generation_id
    assert generation_id is not None

    async with session_maker()() as session:
        await ConversationService(session, responder=responder).run_bot_turn(
            conversation_id, generation_id
        )
    assert message_count(conversation_id, role="bot", body=SCRIPTED_ANSWER) == 1


async def test_transfer_to_bot_rejected_when_bot_is_off(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        _visitor, conversation = await insert_bot_conversation(session, easy)
        alex = User(
            email=ALEX_EMAIL,
            display_name=ALEX_NAME,
            password_hash=hash_password(ALEX_PASSWORD),
            is_admin=False,
            is_active=True,
        )
        session.add(alex)
        await session.commit()
        service = ConversationService(session)
        await service.join(conversation.id, alex)
        easy.bot_enabled = False
        easy.human_enabled = False
        await session.commit()
        conversation_id = conversation.id
        with pytest.raises(CommandError) as exc:
            await service.transfer_to_bot(conversation.id, alex)
        assert exc.value.code == "bot_disabled"
    assert conversation_state(conversation_id) == "human"
    assert message_count(conversation_id, role="system", body=ASSISTANT_LINE) == 0
