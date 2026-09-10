import uuid

from app.chat.outcome_copy import KEEP_HELPING_LINE
from app.db import session_maker
from app.services.conversation_service import ConversationService
from tests.bot_fixtures import (
    FALLBACK,
    FAST_QUERY,
    SCRIPTED_ANSWER,
    WAITING_LINE,
    RecordingResponder,
    insert_bot_conversation,
    seed_brand_articles,
)
from tests.ws_helpers import HOST_ORIGIN, conversation_state, message_count


async def test_no_source_fallback_resets_after_grounded_answer_then_miss_is_count_one(
    migrated_db,
) -> None:
    empty = RecordingResponder()
    grounded = RecordingResponder(answer=SCRIPTED_ANSWER)
    async with session_maker()() as session:
        easy, bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, bg)
        await session.commit()
        bg_conversation_id = conversation.id
        bg_visitor_id = visitor.id
        service = ConversationService(session, responder=empty)
        first = await service.visitor_message(
            bg_conversation_id, bg_visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        if first.generation_id is not None:
            await service.run_bot_turn(bg_conversation_id, first.generation_id)
        await session.refresh(conversation)
        assert conversation_state(bg_conversation_id) == "bot"
        assert conversation.fallback_count == 1
        assert message_count(bg_conversation_id, role="system", body=FALLBACK) == 1

        service_easy = ConversationService(session, responder=grounded)
        visitor_es, convo_es = await insert_bot_conversation(session, easy)
        await session.commit()
        easy_conversation_id = convo_es.id
        easy_visitor_id = visitor_es.id
        hit = await service_easy.visitor_message(
            easy_conversation_id, easy_visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        await service_easy.run_bot_turn(easy_conversation_id, hit.generation_id)
        await session.refresh(convo_es)
        assert convo_es.fallback_count == 0
        assert message_count(easy_conversation_id, role="bot", body=SCRIPTED_ANSWER) == 1

        miss_service = ConversationService(session, responder=RecordingResponder(answer=""))
        miss = await miss_service.visitor_message(
            easy_conversation_id,
            easy_visitor_id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "what is your unpublished internal pricing matrix",
        )
        if miss.generation_id is not None:
            await miss_service.run_bot_turn(easy_conversation_id, miss.generation_id)
        await session.refresh(convo_es)
        assert convo_es.fallback_count == 1
        assert conversation_state(easy_conversation_id) == "bot"
        assert message_count(easy_conversation_id, role="system", body=WAITING_LINE) == 0


async def test_two_consecutive_misses_ask_again_without_queuing(migrated_db) -> None:
    responder = RecordingResponder(answer="")
    async with session_maker()() as session:
        _easy, bg, _timing, _fcra = await seed_brand_articles(session)
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
        second = await service.visitor_message(
            conversation_id,
            visitor_id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "what is your unpublished internal pricing catalog",
        )
        if second.generation_id is not None:
            await service.run_bot_turn(conversation_id, second.generation_id)

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=FALLBACK) == 2
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0
    assert message_count(conversation_id, role="bot") == 0


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
    assert message_count(conversation_id, role="system", body=FALLBACK) == 1
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 1


async def test_explicit_person_request_stays_with_bot_and_does_not_queue(
    migrated_db,
) -> None:
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
    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="bot") == 0
    assert message_count(conversation_id, role="system", body=KEEP_HELPING_LINE) == 1
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0
