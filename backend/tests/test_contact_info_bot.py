"""End-to-end: the bot shares site contact info at sign-off and on direct ask."""

import uuid

from app.chat.outcome_copy import BYE_LINE
from app.db import session_maker
from app.services.conversation_service import ConversationService
from app.services.kb_embedder import FakeEmbedder
from tests.bot_fixtures import RecordingResponder, insert_bot_conversation, insert_site
from tests.ws_helpers import HOST_ORIGIN, message_count


async def test_bye_reply_includes_contact_info_when_site_has_it(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite Support")
        site.contact_info = ["555-123-4567", "support@sample-site.example.com"]
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()
        conversation_id = conversation.id
        service = ConversationService(
            session, responder=RecordingResponder(), embedder=FakeEmbedder()
        )
        result = await service.visitor_message(
            conversation_id, visitor.id, HOST_ORIGIN, uuid.uuid4(), "bye"
        )
        assert result.generation_id is None

    expected = f"{BYE_LINE} You can also reach us at 555-123-4567 or support@sample-site.example.com."
    assert message_count(conversation_id, role="system", body=expected) == 1


async def test_bye_reply_has_no_contact_line_when_site_has_none(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite Support")
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()
        conversation_id = conversation.id
        service = ConversationService(
            session, responder=RecordingResponder(), embedder=FakeEmbedder()
        )
        await service.visitor_message(conversation_id, visitor.id, HOST_ORIGIN, uuid.uuid4(), "bye")

    assert message_count(conversation_id, role="system", body=BYE_LINE) == 1


async def test_direct_contact_question_answers_with_contact_info_without_calling_the_model(
    migrated_db,
) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite Support")
        site.contact_info = ["555-123-4567"]
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()
        conversation_id = conversation.id
        responder = RecordingResponder()
        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        result = await service.visitor_message(
            conversation_id, visitor.id, HOST_ORIGIN, uuid.uuid4(), "how can I contact you"
        )
        assert result.generation_id is None

    assert responder.calls == []
    assert (
        message_count(conversation_id, role="system", body="You can also reach us at 555-123-4567.")
        == 1
    )


async def test_contact_question_falls_through_when_site_has_no_contact_info(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite Support")
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()
        conversation_id = conversation.id
        responder = RecordingResponder(answer="")
        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        result = await service.visitor_message(
            conversation_id, visitor.id, HOST_ORIGIN, uuid.uuid4(), "how can I contact you"
        )
        # No contact_info configured: the request is not intercepted, so the
        # normal grounded flow arms a bot turn instead of the canned reply.
        assert result.generation_id is not None

    assert message_count(conversation_id, role="system") == 0
