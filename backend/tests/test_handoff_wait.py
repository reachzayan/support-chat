"""Visitor-requested handoffs wait for a decision rather than timing out."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import session_maker
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.conversation_service import CommandError, ConversationService
from tests.bot_fixtures import insert_bot_conversation, insert_site
from tests.ws_helpers import HOST_ORIGIN, insert_staff, message_count

START = datetime(2026, 10, 7, 16, tzinfo=UTC)
PROMPT = "Our agents are all currently busy right now. Would you like to wait?"


async def waiting_chat(session):
    site = await insert_site(session, "waiting", "Waiting")
    visitor, chat = await insert_bot_conversation(session, site)
    await session.commit()
    await ConversationService(session).visitor_message(
        chat.id, visitor.id, HOST_ORIGIN, uuid4(), "I need to talk to a person"
    )
    chat.handoff_wait_started_at = START
    chat.last_message_at = START
    await session.commit()
    return visitor, chat


async def test_five_minute_handoff_prompts_once_and_does_not_close_without_an_answer(migrated_db):
    async with session_maker()() as session:
        _, chat = await waiting_chat(session)
        service = ConversationService(session)
        assert await service.tick_idle(chat.id, now=START + timedelta(minutes=4)) is None
        result = await service.tick_idle(chat.id, now=START + timedelta(minutes=5))
        assert result is not None
        assert result.message.body == PROMPT
        assert chat.state == "queued"
        assert chat.handoff_wait_prompt_id == result.message.id
        assert await service.tick_idle(chat.id, now=START + timedelta(hours=1)) is None
        assert chat.state == "queued"
        assert message_count(chat.id, body=PROMPT) == 1
        assert message_count(chat.id, body="This chat has been closed automatically.") == 0


async def test_keep_waiting_restarts_the_prompt_clock_and_duplicate_choice_is_safe(migrated_db):
    async with session_maker()() as session:
        visitor, chat = await waiting_chat(session)
        service = ConversationService(session)
        prompt = await service.tick_idle(chat.id, now=START + timedelta(minutes=5))
        await service.respond_handoff_wait(
            chat.id,
            visitor.id,
            HOST_ORIGIN,
            prompt.message.id,
            True,
            now=START + timedelta(minutes=6),
        )
        assert chat.state == "queued"
        assert chat.handoff_wait_prompt_id is None
        assert await service.tick_idle(chat.id, now=START + timedelta(minutes=10)) is None
        chat_id = chat.id
        with pytest.raises(CommandError, match="stale_wait_prompt"):
            await service.respond_handoff_wait(
                chat.id, visitor.id, HOST_ORIGIN, prompt.message.id, False
            )
        await session.rollback()
        again = await service.tick_idle(chat_id, now=START + timedelta(minutes=11))
        assert again.message.body == PROMPT
        assert message_count(chat_id, body=PROMPT) == 2
        assert message_count(chat_id, body="Thanks for waiting. You're still in the queue.") == 1


async def test_declining_wait_closes_chat_and_clears_attention(migrated_db):
    async with session_maker()() as session:
        visitor, chat = await waiting_chat(session)
        service = ConversationService(session)
        prompt = await service.tick_idle(chat.id, now=START + timedelta(minutes=5))
        result = await service.respond_handoff_wait(
            chat.id, visitor.id, HOST_ORIGIN, prompt.message.id, False
        )
        assert result.conversation.state == "closed"
        assert result.conversation.attention_needed is False
        assert result.conversation.handoff_wait_prompt_id is None
        assert result.message.body == "This chat was closed at your request."


async def test_agent_join_wins_over_a_late_wait_choice(migrated_db):
    agent_id = insert_staff("wait-agent@example.com", "Alex Morgan", "secret")
    async with session_maker()() as session:
        visitor, chat = await waiting_chat(session)
        service = ConversationService(session)
        prompt = await service.tick_idle(chat.id, now=START + timedelta(minutes=5))
        agent = await session.get(User, agent_id)
        await service.join(chat.id, agent)
        chat_id = chat.id
        with pytest.raises(CommandError, match="stale_wait_prompt"):
            await service.respond_handoff_wait(
                chat.id, visitor.id, HOST_ORIGIN, prompt.message.id, False
            )
        await session.rollback()
        loaded = await session.get(Conversation, chat_id)
        assert loaded.state == "human"
        assert loaded.handoff_wait_prompt_id is None


async def test_busy_prompt_is_based_on_handoff_age_even_if_visitor_adds_context(migrated_db):
    async with session_maker()() as session:
        _, chat = await waiting_chat(session)
        chat.last_message_at = START + timedelta(minutes=4)
        await session.commit()
        results = await ConversationService(session).close_expired(now=START + timedelta(minutes=5))
        assert [result.conversation.id for result in results] == [chat.id]
        assert results[0].message.body == PROMPT
        assert chat.state == "queued"


async def test_other_visitor_cannot_answer_wait_prompt(migrated_db):
    async with session_maker()() as session:
        _, chat = await waiting_chat(session)
        service = ConversationService(session)
        prompt = await service.tick_idle(chat.id, now=START + timedelta(minutes=5))
        with pytest.raises(CommandError, match="invalid"):
            await service.respond_handoff_wait(
                chat.id, uuid4(), HOST_ORIGIN, prompt.message.id, False
            )
        await session.rollback()
        rows = await session.scalars(select(Message).where(Message.body == PROMPT))
        assert len(rows.all()) == 1


async def test_retried_wait_choice_after_lost_ack_does_not_repeat_answer_or_reset_clock(
    migrated_db,
):
    async with session_maker()() as session:
        visitor, chat = await waiting_chat(session)
        service = ConversationService(session)
        prompt = await service.tick_idle(chat.id, now=START + timedelta(minutes=5))
        await service.respond_handoff_wait(
            chat.id,
            visitor.id,
            HOST_ORIGIN,
            prompt.message.id,
            True,
            now=START + timedelta(minutes=6),
        )
        retried = await service.respond_handoff_wait(
            chat.id,
            visitor.id,
            HOST_ORIGIN,
            prompt.message.id,
            True,
            now=START + timedelta(minutes=9),
        )
        assert retried.duplicate is True
        assert chat.handoff_wait_started_at == START + timedelta(minutes=6)
        assert message_count(chat.id, body="Keep waiting") == 1
        assert message_count(chat.id, body="Thanks for waiting. You're still in the queue.") == 1


async def test_callback_handoff_stays_in_attention_queue_without_live_wait_prompt(migrated_db):
    async with session_maker()() as session:
        site = await insert_site(session, "callback-wait", "Callback")
        site.human_enabled = False
        visitor, chat = await insert_bot_conversation(session, site)
        await session.commit()
        service = ConversationService(session)
        await service.visitor_message(
            chat.id, visitor.id, HOST_ORIGIN, uuid4(), "I need to talk to a person"
        )
        chat.last_message_at = START
        await session.commit()
        results = await service.close_expired(now=START + timedelta(hours=1))
        assert results == []
        assert chat.state == "queued" and chat.attention_needed is True
        assert message_count(chat.id, body=PROMPT) == 0
        assert message_count(chat.id, body="This chat has been closed automatically.") == 0


async def test_callback_backlog_does_not_block_due_live_wait_prompts_in_bounded_sweep(migrated_db):
    async with session_maker()() as session:
        site = await insert_site(session, "callback-backlog", "Callback")
        site.human_enabled = False
        visitor, callback = await insert_bot_conversation(session, site)
        await session.commit()
        await ConversationService(session).visitor_message(
            callback.id, visitor.id, HOST_ORIGIN, uuid4(), "I need a person"
        )
        callback.last_message_at = START - timedelta(days=1)
        await session.commit()
        _, live = await waiting_chat(session)
        results = await ConversationService(session).close_expired(
            now=START + timedelta(minutes=5),
            limit=1,
        )
        assert [result.conversation.id for result in results] == [live.id]
        assert results[0].message.body == PROMPT
        assert callback.state == "queued"
