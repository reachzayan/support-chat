import uuid

from app.db import session_maker
from app.services.conversation_service import ConversationService
from tests.bot_fixtures import (
    ADA_EMAIL,
    ADA_NAME,
    FALLBACK,
    RecordingResponder,
    insert_bot_conversation,
    insert_site,
)
from tests.ws_helpers import HOST_ORIGIN, conversation_state, message_count

WELCOME_SAMPLESITE = "Hi, welcome to SampleSite Support. How can we help you today?"
WELCOME_SITE_NAME = "Hi, welcome to SampleSite. How can we help you today?"
PAGE_TITLE = "SampleSite Support | Drug Screening & DOT Compliance"


async def test_prechat_inserts_welcome_from_page_title(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        visitor, conversation = await insert_bot_conversation(session, site)
        conversation.state = "prechat"
        conversation.page_title = PAGE_TITLE
        await session.commit()
        result = await ConversationService(session, responder=RecordingResponder()).submit_prechat(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            ADA_NAME,
            ADA_EMAIL,
            "",
            "other",
            "",
        )
        conversation_id = conversation.id

    assert result.generation_id is None
    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=WELCOME_SAMPLESITE) == 1
    assert message_count(conversation_id, role="system", body=FALLBACK) == 0
    assert message_count(conversation_id, role="visitor") == 0


async def test_prechat_welcome_uses_site_name_when_page_title_is_empty(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        visitor, conversation = await insert_bot_conversation(session, site)
        conversation.state = "prechat"
        conversation.page_title = None
        await session.commit()
        await ConversationService(session, responder=RecordingResponder()).submit_prechat(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            ADA_NAME,
            ADA_EMAIL,
            "",
            "other",
            "",
        )
        conversation_id = conversation.id

    assert message_count(conversation_id, role="system", body=WELCOME_SITE_NAME) == 1
    assert message_count(conversation_id, role="system", body=WELCOME_SAMPLESITE) == 0


async def test_repeat_prechat_does_not_duplicate_welcome(migrated_db) -> None:
    submission_id = uuid.uuid4()
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        visitor, conversation = await insert_bot_conversation(session, site)
        conversation.state = "prechat"
        conversation.page_title = PAGE_TITLE
        await session.commit()
        service = ConversationService(session, responder=RecordingResponder())
        await service.submit_prechat(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            submission_id,
            ADA_NAME,
            ADA_EMAIL,
            "",
            "other",
            "",
        )
        await service.submit_prechat(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            submission_id,
            ADA_NAME,
            ADA_EMAIL,
            "",
            "other",
            "",
        )
        conversation_id = conversation.id

    assert message_count(conversation_id, role="system", body=WELCOME_SAMPLESITE) == 1
