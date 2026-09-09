from app.db import session_maker
from app.repositories.handoff_repo import HandoffRepository
from app.services.handoff_service import HandoffService, HandoffTrigger
from tests.bot_fixtures import insert_bot_conversation, insert_site
from tests.ws_helpers import message_count

FIRST_QUESTION = "Need a human about turnaround time"
SECOND_QUESTION = "Still waiting on a specialist"


async def test_open_handoff_returns_existing_unresolved_row_without_duplicate_system_message(
    migrated_db,
) -> None:
    async with session_maker()() as session:
        easy = await insert_site(session, "handoff-idem", "Handoff Idem")
        _visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        conversation_id = conversation.id
        service = HandoffService(session)
        first = await service.open_handoff(
            HandoffTrigger(
                conversation_id=conversation_id,
                reason="visitor_request",
                original_question=FIRST_QUESTION,
            )
        )
        second = await service.open_handoff(
            HandoffTrigger(
                conversation_id=conversation_id,
                reason="visitor_request",
                original_question=SECOND_QUESTION,
            )
        )
        await session.commit()
        handoff_id = first.id

    assert second.id == handoff_id
    assert message_count(conversation_id, role="system") == 1
    async with session_maker()() as session:
        rows = await HandoffRepository(session).get_latest_for_conversation(conversation_id)
        assert rows is not None
        assert rows.id == handoff_id
        assert rows.original_question == FIRST_QUESTION
