import uuid

from sqlalchemy import select

from app.db import session_maker
from app.models.message import Message
from app.models.message_citation import MessageCitation
from app.models.user import User
from app.services.conversation_service import ConversationService
from app.services.kb_embedder import FakeEmbedder
from tests.bot_fixtures import insert_bot_conversation, insert_chunk, insert_site
from tests.ws_helpers import HOST_ORIGIN


async def test_enabled_site_persists_exact_approved_answer_with_citation_spans(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "grounded-site", "Grounded Site")
        chunk = await insert_chunk(
            session,
            site,
            "What DOT services do you provide?",
            "We support DOT drug and alcohol testing and DOT physicals.",
        )
        reviewer = User(
            email="reviewer@grounded.test",
            display_name="Reviewer",
            password_hash="not-used",
            is_admin=True,
        )
        session.add(reviewer)
        await session.flush()
        chunk.approved = True
        chunk.review_status = "approved"
        chunk.reviewed_by = reviewer.id
        from datetime import UTC, datetime

        chunk.reviewed_at = datetime.now(UTC)
        chunk.topic_label = "DOT testing services"
        await session.flush()
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()

        service = ConversationService(session, embedder=FakeEmbedder())
        result = await service.visitor_message(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "What DOT services do you provide?",
        )
        assert result.generation_id is not None
        await service.run_bot_turn(conversation.id, result.generation_id)
        messages = list(
            (
                await session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation.id, Message.role == "bot")
                    .order_by(Message.id)
                )
            ).all()
        )
        citations = list(
            (
                await session.scalars(
                    select(MessageCitation).where(MessageCitation.message_id == messages[-1].id)
                )
            ).all()
        )

    assert messages[-1].body == "We support DOT drug and alcohol testing and DOT physicals."
    assert messages[-1].response_outcome == "exact_answer"
    assert messages[-1].source_chunk_ids == [chunk.id]
    assert len(citations) == 1
    assert citations[0].response_start == 0
    assert citations[0].response_end == len(messages[-1].body)


async def test_provider_failure_persists_a_grounded_extractive_answer(migrated_db) -> None:
    class FailedGroundedResponder:
        async def generate_grounded_draft(self, _turn, _documents):
            return None

    async with session_maker()() as session:
        site = await insert_site(session, "provider-failure", "Provider Failure")
        await insert_chunk(
            session,
            site,
            "Which screening services do you provide?",
            "We provide drug testing and occupational health services.",
        )
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()

        service = ConversationService(
            session,
            responder=FailedGroundedResponder(),
            embedder=FakeEmbedder(),
        )
        result = await service.visitor_message(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "What services do you provide?",
        )
        assert result.generation_id is not None
        await service.run_bot_turn(conversation.id, result.generation_id)
        message = await session.scalar(
            select(Message)
            .where(Message.conversation_id == conversation.id, Message.role == "bot")
            .order_by(Message.id.desc())
            .limit(1)
        )

    assert message is not None
    assert message.body == "We provide drug testing and occupational health services."
    assert message.response_outcome == "synthesized_answer"
    assert message.response_reason_code == "extractive_fallback"
    assert message.system_reason == "answer"
