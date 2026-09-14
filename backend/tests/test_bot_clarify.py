import uuid

from app.chat.outcome_copy import CONTACT_OFFER, TRANSFER_OFFER
from app.db import session_maker
from app.services.conversation_service import ConversationService
from app.services.kb_embedder import FakeEmbedder
from tests.bot_fixtures import (
    RecordingResponder,
    insert_bot_conversation,
    seed_brand_articles,
)
from tests.ws_helpers import HOST_ORIGIN, conversation_state, message_count

SETUP_QUESTION = "can you help us get set up for testing?"
CLARIFY = "Are you setting up pre-employment screens, a random program, or DOT testing?"


async def test_model_authored_question_never_persists_as_a_system_clarification(
    migrated_db,
) -> None:
    responder = RecordingResponder(answer=CLARIFY, selected_ids=[])
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        result = await service.visitor_message(
            conversation.id, visitor.id, HOST_ORIGIN, uuid.uuid4(), SETUP_QUESTION
        )
        if result.generation_id is not None:
            await service.run_bot_turn(conversation.id, result.generation_id)
        conversation_id = conversation.id

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=CLARIFY) == 0
    assert message_count(conversation_id, role="bot", body=CLARIFY) == 0
    assert message_count(conversation_id, role="system", body=TRANSFER_OFFER) == 0
    assert message_count(conversation_id, role="system", body=CONTACT_OFFER) == 0
    assert message_count(conversation_id, role="bot") >= 1
