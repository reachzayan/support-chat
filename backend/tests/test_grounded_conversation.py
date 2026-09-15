import uuid

from sqlalchemy import select
from structlog.testing import capture_logs

from app.chat.outcome_copy import TECH_FAIL_HUMAN, UNCITED_ADVISORY_SUFFIX
from app.db import session_maker
from app.models.message import Message
from app.models.message_citation import MessageCitation
from app.services.conversation_service import ConversationService
from app.services.grounded_response import (
    Citation,
    ModelDraft,
    ResponseDecision,
    ResponseOutcome,
)
from app.services.kb_embedder import FakeEmbedder
from tests.bot_fixtures import (
    RecordingGroundedResponder,
    insert_bot_conversation,
    insert_chunk,
    insert_site,
)
from tests.ws_helpers import HOST_ORIGIN

PARAPHRASE_BODY = "Yes. We handle DOT drug and alcohol testing."
ANSWER_VERBATIM = (
    "We support DOT drug and alcohol testing, random pool management, and DOT physicals."
)


async def test_yes_no_factual_answer_commits_message_and_citation(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "grounded-site", "Grounded Site")
        chunk = await insert_chunk(
            session,
            site,
            "Do you provide DOT drug and alcohol testing?",
            ANSWER_VERBATIM,
        )
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()

        responder = RecordingGroundedResponder(
            body=PARAPHRASE_BODY,
            evidence_id=chunk.id,
            snapshot_id=chunk.snapshot_id,
            source_title=chunk.heading or "DOT",
            source_url="https://legacy.test/dot",
            cited_text=ANSWER_VERBATIM,
        )
        # Align citation metadata with the live page URL/title from insert_chunk.
        from app.models.kb_page import KbPage

        page = await session.get(KbPage, chunk.page_id)
        assert page is not None
        responder.source_title = page.title
        responder.source_url = page.url

        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        result = await service.visitor_message(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "Do you provide drug screening?",
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

    assert messages[-1].body == PARAPHRASE_BODY
    assert messages[-1].response_outcome == "synthesized_answer"
    assert messages[-1].source_chunk_ids == [chunk.id]
    assert len(citations) == 1
    assert citations[0].response_start == 0
    assert citations[0].response_end == len(PARAPHRASE_BODY)


async def test_misspelled_durg_screening_retrieves_same_evidence(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "misspell-site", "Misspell Site")
        chunk = await insert_chunk(
            session,
            site,
            "Do you provide DOT drug and alcohol testing?",
            ANSWER_VERBATIM,
        )
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()

        class CiteRetrieved:
            async def generate_grounded_draft(self, turn, documents, **_kwargs):
                del turn
                unit = documents[0]
                body = PARAPHRASE_BODY
                return ModelDraft(
                    body=body,
                    citations=[
                        Citation(
                            chunk_id=unit.id,
                            snapshot_id=unit.snapshot_id,
                            response_start=0,
                            response_end=len(body),
                            source_start=0,
                            source_end=len(unit.answer_verbatim),
                            cited_text=unit.answer_verbatim,
                            source_title=unit.source_title,
                            source_url=unit.source_url,
                        )
                    ],
                )

        service = ConversationService(session, responder=CiteRetrieved(), embedder=FakeEmbedder())
        result = await service.visitor_message(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "do you provide durg screning?",
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
    assert message.source_chunk_ids == [chunk.id]


async def test_stale_source_at_commit_discards_draft(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "stale-site", "Stale Site")
        chunk = await insert_chunk(
            session,
            site,
            "Do you provide DOT drug and alcohol testing?",
            ANSWER_VERBATIM,
        )
        from app.models.kb_page import KbPage

        page = await session.get(KbPage, chunk.page_id)
        assert page is not None
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        chunk_id = chunk.id
        snapshot_id = chunk.snapshot_id
        page_title = page.title
        page_url = page.url

    class StaleThenRespond:
        async def generate_grounded_draft(self, turn, documents, **_kwargs):
            del turn, documents
            from app.models.kb_chunk import KbChunk

            async with session_maker()() as other:
                row = await other.get(KbChunk, chunk_id)
                assert row is not None
                row.enabled = False
                await other.commit()
            body = PARAPHRASE_BODY
            return ModelDraft(
                body=body,
                citations=[
                    Citation(
                        chunk_id=chunk_id,
                        snapshot_id=snapshot_id,
                        response_start=0,
                        response_end=len(body),
                        source_start=0,
                        source_end=len(ANSWER_VERBATIM),
                        cited_text=ANSWER_VERBATIM,
                        source_title=page_title,
                        source_url=page_url,
                    )
                ],
            )

    async with session_maker()() as session:
        service = ConversationService(
            session, responder=StaleThenRespond(), embedder=FakeEmbedder()
        )
        result = await service.visitor_message(
            conversation_id,
            visitor_id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "Do you provide drug screening?",
        )
        assert result.generation_id is not None
        await service.run_bot_turn(conversation_id, result.generation_id)
        message = await session.scalar(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.role == "bot")
            .order_by(Message.id.desc())
            .limit(1)
        )
        citations = list(
            (
                await session.scalars(
                    select(MessageCitation).where(MessageCitation.message_id == message.id)
                )
            ).all()
        )

    assert message is not None
    assert message.body == TECH_FAIL_HUMAN
    assert message.system_reason == "tech_fail"
    assert citations == []


async def test_finalizer_state_guard_drops_stale_generation(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "guard-site", "Guard Site")
        chunk = await insert_chunk(
            session,
            site,
            "Do you provide DOT drug and alcohol testing?",
            ANSWER_VERBATIM,
        )
        from app.models.kb_page import KbPage

        page = await session.get(KbPage, chunk.page_id)
        assert page is not None
        _visitor, conversation = await insert_bot_conversation(session, site)
        conversation.active_generation_id = uuid.uuid4()
        await session.commit()
        before = (
            await session.scalars(select(Message).where(Message.conversation_id == conversation.id))
        ).all()
        before_count = len(list(before))
        body = PARAPHRASE_BODY
        decision = ResponseDecision(
            ResponseOutcome.SYNTHESIZED_ANSWER,
            None,
            body,
            citations=[
                Citation(
                    chunk_id=chunk.id,
                    snapshot_id=chunk.snapshot_id,
                    response_start=0,
                    response_end=len(body),
                    source_start=0,
                    source_end=len(ANSWER_VERBATIM),
                    cited_text=ANSWER_VERBATIM,
                    source_title=page.title,
                    source_url=page.url,
                )
            ],
        )
        service = ConversationService(session, embedder=FakeEmbedder())
        await service._finalize_grounded_decision(
            conversation.id,
            uuid.uuid4(),  # different generation id
            site.id,
            decision,
        )
        after = list(
            (
                await session.scalars(
                    select(Message).where(Message.conversation_id == conversation.id)
                )
            ).all()
        )
        citations = list(
            (
                await session.scalars(
                    select(MessageCitation)
                    .join(Message)
                    .where(Message.conversation_id == conversation.id)
                )
            ).all()
        )

    assert len(after) == before_count
    assert citations == []


async def test_no_reaches_retrieval_after_assistant_question(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "no-followup", "No Followup")
        await insert_chunk(
            session,
            site,
            "Do you provide DOT drug and alcohol testing?",
            ANSWER_VERBATIM,
        )
        visitor, conversation = await insert_bot_conversation(session, site)
        from app.repositories.message_repo import MessageRepository

        messages = MessageRepository(session)
        await messages.create(
            conversation.id,
            "bot",
            "Would you like DOT services or occupational health?",
            client_message_id=None,
        )
        await session.commit()

        service = ConversationService(session, embedder=FakeEmbedder())
        result = await service.visitor_message(
            conversation.id,
            visitor.id,
            HOST_ORIGIN,
            uuid.uuid4(),
            "no",
        )
        await session.refresh(conversation)
        system_rows = list(
            (
                await session.scalars(
                    select(Message).where(
                        Message.conversation_id == conversation.id, Message.role == "system"
                    )
                )
            ).all()
        )

    assert result.generation_id is not None
    assert conversation.active_generation_id == result.generation_id
    assert system_rows == []


async def test_grounded_turn_log_contains_expected_timing_keys(migrated_db) -> None:
    from structlog.testing import capture_logs

    visitor_text = "Do you provide drug screening?"
    async with session_maker()() as session:
        site = await insert_site(session, "timing-log-site", "Timing Log Site")
        chunk = await insert_chunk(
            session,
            site,
            "Do you provide DOT drug and alcohol testing?",
            ANSWER_VERBATIM,
        )
        from app.models.kb_page import KbPage

        page = await session.get(KbPage, chunk.page_id)
        assert page is not None
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()

        responder = RecordingGroundedResponder(
            body=PARAPHRASE_BODY,
            evidence_id=chunk.id,
            snapshot_id=chunk.snapshot_id,
            source_title=page.title,
            source_url=page.url,
            cited_text=ANSWER_VERBATIM,
            request_id="req_timing_test",
        )
        service = ConversationService(session, responder=responder, embedder=FakeEmbedder())
        with capture_logs() as events:
            result = await service.visitor_message(
                conversation.id,
                visitor.id,
                HOST_ORIGIN,
                uuid.uuid4(),
                visitor_text,
            )
            assert result.generation_id is not None
            await service.run_bot_turn(conversation.id, result.generation_id)

    turn_events = [event for event in events if event.get("event") == "grounded_turn"]
    assert len(turn_events) == 1
    payload = turn_events[0]
    expected_keys = {
        "conversation_id",
        "generation_id",
        "site_id",
        "snapshot_id",
        "request_id",
        "stage_timings",
        "outcome",
        "reason",
        "citation_count",
    }
    assert expected_keys <= set(payload)
    assert payload["request_id"] == "req_timing_test"
    assert payload["snapshot_id"] == str(chunk.snapshot_id)
    assert payload["conversation_id"] == str(conversation.id)
    assert payload["generation_id"] == str(result.generation_id)
    assert payload["site_id"] == str(site.id)
    assert isinstance(payload["citation_count"], int)
    assert payload["outcome"] == "synthesized_answer"
    timings = payload["stage_timings"]
    assert isinstance(timings, dict)
    expected_timing_keys = {
        "history_load",
        "lexical_retrieve",
        "trigram_retrieve",
        "dense_retrieve",
        "embed",
        "provider",
        "citation_parse",
        "validate",
        "liveness_check",
        "commit",
    }
    assert expected_timing_keys <= set(timings)
    assert all(isinstance(value, int) for value in timings.values())


async def test_no_citation_persists_uncited_advisory_and_logs_event(migrated_db) -> None:
    uncited_body = (
        "We provide DOT drug testing for small employers. "
        "A specialist can confirm details for your specific case."
    )

    async with session_maker()() as session:
        site = await insert_site(session, "no-cite-site", "No Cite Site")
        await insert_chunk(
            session,
            site,
            "Do you provide DOT drug and alcohol testing?",
            ANSWER_VERBATIM,
        )
        visitor, conversation = await insert_bot_conversation(session, site)
        await session.commit()

        class UncitedDraft:
            async def generate_grounded_draft(self, turn, documents, **_kwargs):
                del turn, documents
                return ModelDraft(body=uncited_body, citations=[], request_id="req_no_cite")

        service = ConversationService(session, responder=UncitedDraft(), embedder=FakeEmbedder())
        with capture_logs() as events:
            result = await service.visitor_message(
                conversation.id,
                visitor.id,
                HOST_ORIGIN,
                uuid.uuid4(),
                "I have a company of 10 employees and I want drug testing for all of them",
            )
            assert result.generation_id is not None
            await service.run_bot_turn(conversation.id, result.generation_id)
        message = await session.scalar(
            select(Message)
            .where(Message.conversation_id == conversation.id, Message.role == "bot")
            .order_by(Message.id.desc())
            .limit(1)
        )
        citations = list(
            (
                await session.scalars(
                    select(MessageCitation).where(MessageCitation.message_id == message.id)
                )
            ).all()
        )

    assert message is not None
    assert message.body.startswith(uncited_body)
    assert message.body.endswith(UNCITED_ADVISORY_SUFFIX)
    assert message.system_reason == "uncited_advisory"
    assert message.response_reason_code == "uncited_advisory"
    assert message.response_outcome == "synthesized_answer"
    assert citations == []
    advisory_events = [
        event for event in events if event.get("event") == "grounded_uncited_advisory"
    ]
    assert len(advisory_events) == 1
    assert advisory_events[0]["request_id"] == "req_no_cite"
    assert advisory_events[0]["generation_id"] == str(result.generation_id)
    assert advisory_events[0]["body_chars"] == len(uncited_body)
