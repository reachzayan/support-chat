"""Latency paths must preserve the same grounded persistence contract."""

from uuid import uuid4

from sqlalchemy import select

from app.db import session_maker
from app.models.kb_page import KbPage
from app.models.message import Message
from app.services.conversation_service import ConversationService
from tests.bot_fixtures import (
    RecordingGroundedResponder,
    insert_bot_conversation,
    insert_chunk,
    insert_site,
)
from tests.ws_helpers import HOST_ORIGIN


class MemoryRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        del ex
        self.store[key] = value


async def _send(service, conversation, visitor, text):
    accepted = await service.visitor_message(
        conversation.id, visitor.id, HOST_ORIGIN, uuid4(), text
    )
    await service.run_bot_turn(conversation.id, accepted.generation_id)


async def test_exact_response_cache_is_cross_conversation_but_not_used_for_followups(
    migrated_db, monkeypatch
):
    redis = MemoryRedis()
    monkeypatch.setattr("app.services.response_cache.get_redis", lambda: redis)
    async with session_maker()() as session:
        site = await insert_site(session, "response-cache", "Data Solutions")
        chunk = await insert_chunk(
            session, site, "SampleMail", "SampleMail verifies mailing addresses.", "mail"
        )
        page = await session.get(KbPage, chunk.page_id)
        first_visitor, first_conversation = await insert_bot_conversation(session, site)
        second_visitor, second_conversation = await insert_bot_conversation(session, site)
        await session.commit()
        responder = RecordingGroundedResponder(
            "SampleMail verifies mailing addresses.",
            chunk.id,
            chunk.snapshot_id,
            page.title,
            page.url,
            chunk.answer_verbatim,
        )
        from app.services.kb_embedder import FakeEmbedder

        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())

        question = "What does SampleMail verify?"
        await _send(service, first_conversation, first_visitor, question)
        await _send(service, second_conversation, second_visitor, question)
        assert len(responder.calls) == 1

        await _send(service, second_conversation, second_visitor, question)
        assert len(responder.calls) == 2
        replies = list(
            (
                await session.scalars(
                    select(Message)
                    .where(Message.conversation_id == second_conversation.id, Message.role == "bot")
                    .order_by(Message.id)
                )
            ).all()
        )
        assert [row.body for row in replies] == [
            "SampleMail verifies mailing addresses.",
            "SampleMail verifies mailing addresses.",
        ]
        assert all(row.citations for row in replies)
