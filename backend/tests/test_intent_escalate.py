import uuid

from sqlalchemy import select

from app.chat.outcome_copy import INSUFFICIENT_HUMAN
from app.db import session_maker
from app.models.message import Message
from app.services.conversation_service import ConversationService
from app.services.kb_embedder import FakeEmbedder
from tests.bot_fixtures import (
    FAST_QUERY,
    SCRIPTED_ANSWER,
    WAITING_LINE,
    RecordingResponder,
    insert_bot_conversation,
    seed_brand_articles,
)
from tests.ws_helpers import HOST_ORIGIN, conversation_state, message_count

CLARIFY_SCOPE_LINE = "What would you like to know about screening or compliance?"


async def test_grounded_answer_resets_fallback_before_next_miss(
    migrated_db,
) -> None:
    empty = RecordingResponder(answer="")
    grounded = RecordingResponder(answer=SCRIPTED_ANSWER)
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        service = ConversationService(session, responder=empty, embedder=FakeEmbedder())
        first = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        if first.generation_id is not None:
            await service.run_bot_turn(conversation_id, first.generation_id)
        await session.refresh(conversation)
        assert conversation_state(conversation_id) == "bot"
        assert conversation.fallback_count == 1

        grounded_service = ConversationService(session, responder=grounded, embedder=FakeEmbedder())
        hit = await grounded_service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        assert hit.generation_id is not None
        await grounded_service.run_bot_turn(conversation_id, hit.generation_id)
        await session.refresh(conversation)
        assert conversation.fallback_count == 0
        assert message_count(conversation_id, role="bot", body=SCRIPTED_ANSWER) == 1

        miss_service = ConversationService(
            session, responder=RecordingResponder(answer=""), embedder=FakeEmbedder()
        )
        miss = await miss_service.visitor_message(
            conversation_id,
            visitor_id,
            HOST_ORIGIN,
            uuid.uuid4(),
            FAST_QUERY,
        )
        if miss.generation_id is not None:
            await miss_service.run_bot_turn(conversation_id, miss.generation_id)
        await session.refresh(conversation)
        assert conversation.fallback_count == 1
        assert conversation_state(conversation_id) == "bot"
        assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0


async def test_two_consecutive_no_evidence_misses_clarify_then_offer_specialist(
    migrated_db,
) -> None:
    responder = RecordingResponder(answer="")
    async with session_maker()() as session:
        from tests.bot_fixtures import insert_site

        site = await insert_site(session, "empty-kb-site", "Empty KB Site")
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        first = await service.visitor_message(
            conversation_id,
            visitor_id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "Do you offer biometric screening?",
        )
        if first.generation_id is not None:
            await service.run_bot_turn(conversation_id, first.generation_id)
        second = await service.visitor_message(
            conversation_id,
            visitor_id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "I mean biometric screening for employees",
        )
        if second.generation_id is not None:
            await service.run_bot_turn(conversation_id, second.generation_id)

        replies = list(
            (
                await session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id, Message.role == "bot")
                    .order_by(Message.id)
                )
            ).all()
        )

    assert conversation_state(conversation_id) == "bot"
    assert [reply.body for reply in replies] == [CLARIFY_SCOPE_LINE, INSUFFICIENT_HUMAN]
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0


async def test_yes_after_miss_offer_queues_with_waiting_line(migrated_db) -> None:
    responder = RecordingResponder(answer="")
    async with session_maker()() as session:
        _easy, bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, bg)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        service = ConversationService(session, responder=responder)
        miss = await service.visitor_message(
            conversation_id,
            visitor_id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "what is your unpublished internal pricing matrix",
        )
        if miss.generation_id is not None:
            await service.run_bot_turn(conversation_id, miss.generation_id)
        yes = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), "yes"
        )
        if yes.generation_id is not None:
            await service.run_bot_turn(conversation_id, yes.generation_id)

    assert conversation_state(conversation_id) == "queued"
    assert message_count(conversation_id, role="bot") == 1
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 1


async def test_explicit_person_request_queues_with_waiting_line(migrated_db) -> None:
    responder = RecordingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        service = ConversationService(session, responder=responder)
        result = await service.visitor_message(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "Talk to a person",
        )
        if result.generation_id is not None:
            await service.run_bot_turn(conversation.id, result.generation_id)
        conversation_id = conversation.id

    assert responder.calls == []
    assert conversation_state(conversation_id) == "queued"
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 1
