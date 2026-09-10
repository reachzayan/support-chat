import uuid

import pytest
from sqlalchemy import select

from app.db import session_maker
from app.llm.bot_responder import BotResponder
from app.models.kb_chunk import KbChunk
from app.models.message import Message
from app.services.full_context import answer_full_context, conversation_window_messages
from app.services.pii_redactor import REDACTED, redact_for_model
from tests.bot_fixtures import (
    EASY_BODY,
    SCRIPTED_ANSWER,
    insert_bot_conversation,
    insert_chunk,
    seed_brand_articles,
)

PRIOR_VISITOR_LINE = "My email is ada@example.com and phone is (555) 867-5309"
CURRENT_VISITOR_LINE = "How fast are DOT results?"
KB_CONTACT_SNIPPET = "Call billing at support@sample-site.example.com or 800-555-0199."


def _fake_anthropic_recording(captured: dict):
    class FakeMessages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            block = type("Block", (), {"type": "text", "text": SCRIPTED_ANSWER})()
            return type("Response", (), {"content": [block]})()

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            captured["client_kwargs"] = kwargs
            self.messages = FakeMessages()

        async def close(self) -> None:
            captured["closed"] = True

    return FakeClient


def test_redact_for_model_masks_email_phone_and_existing_pii_literals() -> None:
    raw = (
        "SSN 123-45-6789, DL A1234567, plate AB-1234, DOB 1990-01-15, "
        "email ada@example.com, phone (555) 867-5309 and 8005550199"
    )
    redacted = redact_for_model(raw)
    assert "123-45-6789" not in redacted
    assert "A1234567" not in redacted
    assert "AB-1234" not in redacted
    assert "1990-01-15" not in redacted
    assert "ada@example.com" not in redacted
    assert "(555) 867-5309" not in redacted
    assert "8005550199" not in redacted
    assert redacted.count(REDACTED) >= 7


@pytest.mark.asyncio
async def test_bot_responder_sends_redacted_prior_turns(migrated_db, monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "app.llm.bot_responder.AsyncAnthropic",
        _fake_anthropic_recording(captured),
        raising=False,
    )
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        chunk = await insert_chunk(session, easy, "Timing", EASY_BODY)
        await session.commit()
        site = easy
        documents = [chunk]

    prior = [
        {"role": "user", "content": redact_for_model(PRIOR_VISITOR_LINE)},
        {"role": "assistant", "content": "Earlier bot reply must not leak either."},
    ]
    await BotResponder().generate_from_documents(
        site=site,
        visitor_text=CURRENT_VISITOR_LINE,
        documents=documents,
        prior_messages=prior,
    )

    messages = captured.get("messages") or []
    roles = [item.get("role") for item in messages if isinstance(item, dict)]
    assert roles[:2] == ["user", "assistant"]
    serialized = str(messages)
    assert "Earlier bot reply must not leak either." in serialized
    assert CURRENT_VISITOR_LINE in serialized
    assert PRIOR_VISITOR_LINE not in serialized
    assert "ada@example.com" not in serialized
    assert REDACTED in serialized


@pytest.mark.asyncio
async def test_bot_responder_redacts_kb_document_fields_before_provider(
    migrated_db, monkeypatch
) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "app.llm.bot_responder.AsyncAnthropic",
        _fake_anthropic_recording(captured),
        raising=False,
    )
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        chunk = await insert_chunk(session, easy, "Billing", KB_CONTACT_SNIPPET)
        await session.commit()
        site = easy

    await BotResponder().generate_from_documents(
        site=site,
        visitor_text=CURRENT_VISITOR_LINE,
        documents=[chunk],
        prior_messages=[],
    )

    serialized = str(captured.get("messages") or [])
    assert "support@sample-site.example.com" not in serialized
    assert "800-555-0199" not in serialized
    assert REDACTED in serialized


@pytest.mark.asyncio
async def test_full_context_turn_passes_redacted_conversation_window(
    migrated_db, monkeypatch
) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "app.llm.bot_responder.AsyncAnthropic",
        _fake_anthropic_recording(captured),
        raising=False,
    )
    async with session_maker()() as session:
        easy, _bg, timing, _fcra = await seed_brand_articles(session)
        _visitor, conversation = await insert_bot_conversation(session, easy)
        session.add(
            Message(
                conversation_id=conversation.id,
                role="visitor",
                body=PRIOR_VISITOR_LINE,
                client_message_id=uuid.uuid4(),
            )
        )
        session.add(
            Message(
                conversation_id=conversation.id,
                role="bot",
                body=SCRIPTED_ANSWER,
                source_chunk_ids=[timing.chunk_id],
            )
        )
        await session.commit()
        rows = (
            (
                await session.execute(
                    select(Message).where(Message.conversation_id == conversation.id)
                )
            )
            .scalars()
            .all()
        )
        assert conversation_window_messages(rows)
        chunk = await session.get(KbChunk, timing.chunk_id)
        assert chunk is not None
        await answer_full_context(
            session,
            easy,
            [chunk.snapshot_id],
            rows,
            CURRENT_VISITOR_LINE,
        )

    serialized = str(captured.get("messages") or [])
    assert PRIOR_VISITOR_LINE not in serialized
    assert "ada@example.com" not in serialized
    assert CURRENT_VISITOR_LINE in serialized
    assert REDACTED in serialized
    assert SCRIPTED_ANSWER in serialized
