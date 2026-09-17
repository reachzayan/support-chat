import uuid

from sqlalchemy import select

from app.chat.outcome_copy import KEEP_HELPING_LINE, REPEATED_MISS_HUMAN, TECH_FAIL_HUMAN
from app.db import session_maker
from app.models.message import Message
from app.services.conversation_service import ConversationService
from app.services.grounded_response import ModelDraft
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
PRODUCTS_CLARIFY = "What would you like to know about our products or services?"


class ClarifyingResponder:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_grounded_draft(self, _turn, _documents, **_kwargs) -> ModelDraft:
        self.calls += 1
        return ModelDraft(body="Which payroll policy do you mean?", citations=[])


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


async def test_two_consecutive_no_evidence_misses_clarify_then_queue_specialist(
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

    assert conversation_state(conversation_id) == "queued"
    assert [reply.body for reply in replies] == [PRODUCTS_CLARIFY]
    assert message_count(conversation_id, role="system", body=REPEATED_MISS_HUMAN) == 1


async def test_two_consecutive_retrieval_misses_queue_specialist(
    migrated_db,
) -> None:
    responder = ClarifyingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        conversation_id = conversation.id
        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        first = await service.visitor_message(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "What is the unpublished lunar payroll rate?",
        )
        assert first.generation_id is not None
        await service.run_bot_turn(conversation.id, first.generation_id)
        await session.refresh(conversation)
        assert conversation.state == "bot"
        assert conversation.fallback_count == 1

        second = await service.visitor_message(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "I mean the internal lunar payroll rate nobody publishes.",
        )
        assert second.generation_id is not None
        await service.run_bot_turn(conversation.id, second.generation_id)

    assert responder.calls == 0
    assert conversation_state(conversation_id) == "queued"
    assert message_count(conversation_id, role="bot", body=CLARIFY_SCOPE_LINE) == 1
    assert message_count(conversation_id, role="system", body=REPEATED_MISS_HUMAN) == 1


async def test_in_scope_question_after_a_retrieval_miss_still_clarifies(
    migrated_db,
) -> None:
    class RejectingResponder:
        calls = 0

        async def generate_grounded_draft(self, _turn, _documents, **_kwargs) -> ModelDraft:
            self.calls += 1
            return ModelDraft(body="Results come back in 12 hours.", citations=[])

    responder = RejectingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        miss = await service.visitor_message(
            conversation_id,
            visitor_id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "what is your unpublished internal pricing matrix",
        )
        assert miss.generation_id is not None
        await service.run_bot_turn(conversation_id, miss.generation_id)
        await session.refresh(conversation)
        assert conversation.fallback_count == 1
        follow = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        assert follow.generation_id is not None
        await service.run_bot_turn(conversation_id, follow.generation_id)
        await session.refresh(conversation)

    assert responder.calls == 1
    assert conversation_state(conversation_id) == "bot"
    assert conversation.fallback_count == 2
    assert message_count(conversation_id, role="bot", body=CLARIFY_SCOPE_LINE) == 2
    assert message_count(conversation_id, role="system", body=REPEATED_MISS_HUMAN) == 0
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0


async def test_page_followup_does_not_hand_off_the_next_in_scope_question(
    migrated_db,
) -> None:
    responder = RecordingResponder(answer=SCRIPTED_ANSWER)
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        first = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        assert first.generation_id is not None
        await service.run_bot_turn(conversation_id, first.generation_id)
        follow = await service.visitor_message(
            conversation_id,
            visitor_id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "Which page did that come from?",
        )
        if follow.generation_id is not None:
            await service.run_bot_turn(conversation_id, follow.generation_id)
        await session.refresh(conversation)
        assert conversation.fallback_count == 0
        assert conversation.state == "bot"
        assert message_count(conversation_id, role="bot", body=KEEP_HELPING_LINE) == 1
        bots = list(
            (
                await session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id, Message.role == "bot")
                    .order_by(Message.id)
                )
            ).all()
        )
        assert len(bots) == 2
        assert bots[0].source_urls
        assert bots[1].source_urls == bots[0].source_urls
        again = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        assert again.generation_id is not None
        await service.run_bot_turn(conversation_id, again.generation_id)

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="bot", body=SCRIPTED_ANSWER) == 2
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0


async def test_where_did_you_get_that_keeps_helping_after_an_answer(migrated_db) -> None:
    responder = RecordingResponder(answer=SCRIPTED_ANSWER)
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        first = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        assert first.generation_id is not None
        await service.run_bot_turn(conversation_id, first.generation_id)
        follow = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), "Where did you get that?"
        )
        if follow.generation_id is not None:
            await service.run_bot_turn(conversation_id, follow.generation_id)
        await session.refresh(conversation)
        assert conversation.fallback_count == 0

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="bot", body=KEEP_HELPING_LINE) == 1
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0


async def test_two_model_canned_clarifies_queue_on_the_second(migrated_db) -> None:
    class CannedResponder:
        calls = 0

        async def generate_grounded_draft(self, _turn, _documents, **_kwargs) -> ModelDraft:
            self.calls += 1
            return ModelDraft(body=CLARIFY_SCOPE_LINE, citations=[])

    responder = CannedResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        first = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        assert first.generation_id is not None
        await service.run_bot_turn(conversation_id, first.generation_id)
        second = await service.visitor_message(
            conversation_id, visitor_id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        assert second.generation_id is not None
        await service.run_bot_turn(conversation_id, second.generation_id)

    assert responder.calls == 2
    assert conversation_state(conversation_id) == "queued"
    assert message_count(conversation_id, role="bot", body=CLARIFY_SCOPE_LINE) == 1
    assert message_count(conversation_id, role="system", body=REPEATED_MISS_HUMAN) == 1


async def test_bot_turn_exception_persists_tech_fail_instead_of_silence(migrated_db) -> None:
    class BoomService(ConversationService):
        async def _retrieve_evidence(self, *args, **kwargs):
            raise RuntimeError("retrieve exploded")

    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        conversation_id = conversation.id
        service = BoomService(session, responder=RecordingResponder(), embedder=FakeEmbedder())
        first = await service.visitor_message(
            conversation_id, visitor.id, HOST_ORIGIN, uuid.uuid4(), FAST_QUERY
        )
        assert first.generation_id is not None
        await service.run_bot_turn(conversation_id, first.generation_id)

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="bot", body=TECH_FAIL_HUMAN) == 1
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0


async def test_yes_after_scope_clarification_does_not_queue(migrated_db) -> None:
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

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="bot") >= 1
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0


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
            "I want to speak with a person.",
        )
        if result.generation_id is not None:
            await service.run_bot_turn(conversation.id, result.generation_id)
        conversation_id = conversation.id

    assert responder.calls == []
    assert conversation_state(conversation_id) == "queued"
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 1
