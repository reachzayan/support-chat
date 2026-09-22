import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db import session_maker
from app.models.kb_page import KbPage
from app.models.kb_source import KbSource
from tests.bot_fixtures import insert_site


async def test_tenant_scoped_fks_replace_unscoped_duplicates(migrated_db) -> None:
    async with session_maker()() as session:
        names = set(
            (
                await session.scalars(
                    text(
                        """
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid IN ('messages'::regclass, 'handoff_contexts'::regclass)
                          AND contype = 'f'
                        """
                    )
                )
            ).all()
        )

    assert "messages_conversation_id_fkey" not in names
    assert "fk_messages_snapshot_id" not in names
    assert "handoff_contexts_conversation_id_fkey" not in names
    assert "handoff_contexts_snapshot_id_fkey" not in names


async def test_cross_site_kb_page_source_insert_is_rejected(migrated_db) -> None:
    async with session_maker()() as session:
        easy = await insert_site(session, "samplesite", "SampleSite")
        other = await insert_site(session, "background", "Sample Services")
        source = KbSource(
            site_id=easy.id,
            start_url="https://sample-site.example.com/faq",
            mode="list",
            seed_urls=[],
            include_globs=[],
            exclude_globs=[],
        )
        session.add(source)
        await session.flush()
        page = KbPage(
            source_id=source.id,
            site_id=other.id,
            url="https://sample-services.example.com/faq",
            title="FAQ",
            content_text="",
            content_sha256="abc",
            http_status=200,
        )
        session.add(page)
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_cross_site_message_citation_insert_is_rejected(migrated_db) -> None:
    from app.models.conversation import Conversation
    from app.models.kb_chunk import KbChunk
    from app.models.kb_snapshot import KbSnapshot
    from app.models.message import Message
    from app.models.message_citation import MessageCitation
    from app.models.visitor import Visitor

    async with session_maker()() as session:
        easy = await insert_site(session, "samplesite", "SampleSite")
        other = await insert_site(session, "background", "Sample Services")
        visitor = Visitor(site_id=easy.id, resume_token_hash="cite-hash")
        session.add(visitor)
        await session.flush()
        conversation = Conversation(site_id=easy.id, visitor_id=visitor.id, state="bot")
        session.add(conversation)
        await session.flush()
        message = Message(
            conversation_id=conversation.id,
            site_id=easy.id,
            role="bot",
            body="Could you share a bit more about what you need?",
            source_chunk_ids=None,
            system_reason="clarify",
        )
        session.add(message)
        other_source = KbSource(
            site_id=other.id,
            start_url="https://sample-services.example.com/faq",
            mode="list",
            seed_urls=[],
            include_globs=[],
            exclude_globs=[],
        )
        session.add(other_source)
        await session.flush()
        other_page = KbPage(
            source_id=other_source.id,
            site_id=other.id,
            url="https://sample-services.example.com/faq",
            title="FAQ",
            content_text="body",
            content_sha256="def",
            http_status=200,
        )
        session.add(other_page)
        await session.flush()
        snapshot = KbSnapshot(
            source_id=other_source.id,
            site_id=other.id,
            state="live",
            content_hash="hash",
            token_estimate=1,
        )
        session.add(snapshot)
        await session.flush()
        chunk = KbChunk(
            page_id=other_page.id,
            site_id=other.id,
            snapshot_id=snapshot.id,
            kind="faq",
            heading="Timing",
            body="24-48 hours",
            answer_verbatim="24-48 hours",
            ordinal=0,
            enabled=True,
        )
        session.add(chunk)
        await session.flush()
        session.add(
            MessageCitation(
                message_id=message.id,
                site_id=easy.id,
                chunk_id=chunk.id,
                snapshot_id=snapshot.id,
                response_start=0,
                response_end=10,
                source_start=0,
                source_end=10,
                cited_text="24-48 hours",
                source_title="Timing",
                source_url="https://sample-services.example.com/faq",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_cross_site_source_chunk_ids_update_is_rejected(migrated_db) -> None:
    from app.models.conversation import Conversation
    from app.models.kb_chunk import KbChunk
    from app.models.kb_snapshot import KbSnapshot
    from app.models.message import Message
    from app.models.visitor import Visitor

    async with session_maker()() as session:
        easy = await insert_site(session, "samplesite", "SampleSite")
        other = await insert_site(session, "background", "Sample Services")
        visitor = Visitor(site_id=easy.id, resume_token_hash="chunk-hash")
        session.add(visitor)
        await session.flush()
        conversation = Conversation(site_id=easy.id, visitor_id=visitor.id, state="bot")
        session.add(conversation)
        await session.flush()
        message = Message(
            conversation_id=conversation.id,
            site_id=easy.id,
            role="bot",
            body="Could you share a bit more about what you need?",
            source_chunk_ids=None,
            system_reason="clarify",
        )
        session.add(message)
        other_source = KbSource(
            site_id=other.id,
            start_url="https://sample-services.example.com/faq",
            mode="list",
            seed_urls=[],
            include_globs=[],
            exclude_globs=[],
        )
        session.add(other_source)
        await session.flush()
        other_page = KbPage(
            source_id=other_source.id,
            site_id=other.id,
            url="https://sample-services.example.com/faq",
            title="FAQ",
            content_text="body",
            content_sha256="ghi",
            http_status=200,
        )
        session.add(other_page)
        await session.flush()
        snapshot = KbSnapshot(
            source_id=other_source.id,
            site_id=other.id,
            state="live",
            content_hash="hash2",
            token_estimate=1,
        )
        session.add(snapshot)
        await session.flush()
        chunk = KbChunk(
            page_id=other_page.id,
            site_id=other.id,
            snapshot_id=snapshot.id,
            kind="faq",
            heading="Timing",
            body="24-48 hours",
            answer_verbatim="24-48 hours",
            ordinal=0,
            enabled=True,
        )
        session.add(chunk)
        await session.flush()
        await session.commit()
        message.source_chunk_ids = [chunk.id]
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_deleting_cited_resources_preserves_citation_site(migrated_db) -> None:
    from app.models.kb_snapshot import KbSnapshot
    from app.models.message import Message
    from app.models.message_citation import MessageCitation
    from tests.bot_fixtures import insert_bot_conversation, insert_chunk

    async with session_maker()() as session:
        site = await insert_site(session, "citation-delete", "Citation Delete")
        chunk = await insert_chunk(session, site, "Timing", "Results take 24-48 hours.")
        snapshot_id = chunk.snapshot_id
        _, conversation = await insert_bot_conversation(session, site)
        message = Message(
            conversation_id=conversation.id,
            site_id=site.id,
            role="bot",
            body="Results take 24-48 hours.",
            source_chunk_ids=[chunk.id],
            snapshot_id=snapshot_id,
            system_reason="answer",
        )
        session.add(message)
        await session.flush()
        citation = MessageCitation(
            message_id=message.id,
            site_id=site.id,
            chunk_id=chunk.id,
            snapshot_id=snapshot_id,
            response_start=0,
            response_end=27,
            source_start=0,
            source_end=27,
            cited_text="Results take 24-48 hours.",
            source_title="Timing",
            source_url="https://legacy.test/timing",
        )
        session.add(citation)
        await session.flush()

        await session.delete(chunk)
        await session.flush()
        await session.refresh(citation)
        assert citation.chunk_id is None
        assert citation.site_id == site.id

        snapshot = await session.scalar(select(KbSnapshot).where(KbSnapshot.id == snapshot_id))
        assert snapshot is not None
        await session.delete(snapshot)
        await session.flush()
        await session.refresh(citation)
        assert citation.snapshot_id is None
        assert citation.site_id == site.id
