import uuid

from app.db import session_maker
from app.services.conversation_service import ConversationService
from app.services.kb_embedder import FakeEmbedder
from tests.bot_fixtures import (
    FALLBACK,
    RecordingResponder,
    insert_bot_conversation,
    seed_brand_articles,
)
from tests.ws_helpers import HOST_ORIGIN, conversation_state, message_count


async def _send_bot_turn(session, site, body: str):
    visitor, conversation = await insert_bot_conversation(session, site)
    await session.commit()
    service = ConversationService(session, responder=RecordingResponder(), embedder=FakeEmbedder())
    result = await service.visitor_message(
        conversation.id, visitor.id, HOST_ORIGIN, uuid.uuid4(), body
    )
    if result.generation_id is not None:
        await service.run_bot_turn(conversation.id, result.generation_id)
    return conversation.id


async def test_greeting_does_not_claim_empty_knowledge_base(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        service = ConversationService(
            session, responder=RecordingResponder(), embedder=FakeEmbedder()
        )
        result = await service.visitor_message(
            conversation.id, visitor.id, HOST_ORIGIN, uuid.uuid4(), "hi"
        )
        if result.generation_id is not None:
            await service.run_bot_turn(conversation.id, result.generation_id)
        conversation_id = conversation.id

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=FALLBACK) == 0
    assert message_count(conversation_id, role="bot") == 0


async def test_bye_does_not_offer_a_human_transfer(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id = await _send_bot_turn(session, easy, "bye")

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=FALLBACK) == 0
    assert message_count(conversation_id, role="bot") == 0
