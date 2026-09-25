from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import session_maker
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.visitor import Visitor
from app.settings import Settings
from scripts.purge_expired_chats import purge_expired
from tests.bot_fixtures import insert_site

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
CUTOFF = NOW - timedelta(days=30)


async def _make_chat(session, site, *, last_message_at, resume_hash: str) -> tuple:
    visitor = Visitor(site_id=site.id, resume_token_hash=resume_hash)
    session.add(visitor)
    await session.flush()
    conversation = Conversation(
        site_id=site.id,
        visitor_id=visitor.id,
        state="closed",
        last_message_at=last_message_at,
    )
    session.add(conversation)
    await session.flush()
    session.add(Message(conversation_id=conversation.id, role="system", body="closed"))
    await session.flush()
    return visitor, conversation


async def test_purge_removes_only_expired_transcript_and_orphan_visitor(migrated_db) -> None:
    async with session_maker()() as session:
        easy = await insert_site(session, "samplesite", "SampleSite")
        bg = await insert_site(session, "backgroundchecks", "Sample Services")
        expired_v, expired_c = await _make_chat(
            session, easy, last_message_at=CUTOFF - timedelta(hours=1), resume_hash="expired-hash"
        )
        boundary_v, boundary_c = await _make_chat(
            session, easy, last_message_at=CUTOFF, resume_hash="boundary-hash"
        )
        other_v, other_c = await _make_chat(
            session, bg, last_message_at=NOW - timedelta(days=1), resume_hash="other-hash"
        )
        await session.commit()
        expired_vid, expired_cid = expired_v.id, expired_c.id
        keep_visitors = {boundary_v.id, other_v.id}
        keep_conversations = {boundary_c.id, other_c.id}

    counts = await purge_expired(now=NOW, dry_run=True)
    assert counts == {"conversations": 1, "visitors": 1}
    async with session_maker()() as session:
        assert await session.get(Conversation, expired_cid) is not None

    counts = await purge_expired(now=NOW, dry_run=False)
    assert counts == {"conversations": 1, "visitors": 1}
    async with session_maker()() as session:
        assert await session.get(Conversation, expired_cid) is None
        assert await session.get(Visitor, expired_vid) is None
        remaining_conversations = set((await session.execute(select(Conversation.id))).scalars())
        remaining_visitors = set((await session.execute(select(Visitor.id))).scalars())
    assert remaining_conversations == keep_conversations
    assert remaining_visitors == keep_visitors


def test_production_startup_rejects_missing_retention() -> None:
    with pytest.raises(ValueError, match="must be a positive integer"):
        Settings(
            database_url="postgresql://chat:chat@127.0.0.1:55432/support_chat_test",
            jwt_secret="j" * 64,
            widget_token_secret="w" * 64,
            rate_key_secret="r" * 64,
            app_env="production",
            chat_retention_days=0,
        )
