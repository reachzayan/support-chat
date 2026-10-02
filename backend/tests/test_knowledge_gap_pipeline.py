"""A bot miss becomes a hit; hits cluster into one gap per repeated question.

Oracles: the rule written for this feature. A miss is a visitor question the bot could
not answer from the site. Questions with cosine similarity >= 0.82 share a gap; below it,
or on another website, they never do. Vectors are 2-D directions padded to the column size,
so cos(A, B) = 0.9 and cos(A, D) = 0.8 are hand-computed, not produced by the code.
"""

import uuid

from sqlalchemy import select

from app.db import session_maker
from app.models.canned_reply import CannedReply
from app.models.conversation import Conversation
from app.models.kb_page import KbPage
from app.models.knowledge_gap import KnowledgeGap, KnowledgeGapHit
from app.models.message import Message
from app.models.site import Site
from app.models.visitor import Visitor
from app.repositories.knowledge_gap_repo import KnowledgeGapRepository
from app.services.conversation_service import ConversationService
from app.services.grounded_response import ModelDraft
from app.services.kb_embedder import FakeEmbedder
from app.services.knowledge_gap_service import KnowledgeGapService
from app.workers import durable_work
from tests.bot_fixtures import (
    RecordingGroundedResponder,
    insert_bot_conversation,
    insert_chunk,
    insert_site,
)
from tests.ws_helpers import HOST_ORIGIN

ENROLL = "How do I enroll a driver?"
ENROLL_PARAPHRASE = "What is the enrollment process?"
PRICING = "How much does it cost?"
NEAR_MISS = "Where do I sign drivers up?"
VECTOR_SIZE = 1536
ANSWER_VERBATIM = (
    "We support DOT drug and alcohol testing, random pool management, and DOT physicals."
)
CANNED_BODY = "Most negative results are reported within 24-48 hours."


def _vector(x: float, y: float) -> list[float]:
    return [x, y] + [0.0] * (VECTOR_SIZE - 2)


A = _vector(1.0, 0.0)
B = _vector(0.9, 0.4359)  # cos(A, B) = 0.9
C = _vector(0.0, 1.0)  # cos(A, C) = 0.0
D = _vector(0.8, 0.6)  # cos(A, D) = 0.8


class StubEmbedder:
    """Maps known texts to fixed vectors; unknown text, or vectors=None, has no embedding."""

    embedder_id = "stub:test"
    dim = VECTOR_SIZE

    def __init__(self, vectors: dict[str, list[float]] | None) -> None:
        self._vectors = vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("gap clustering embeds one question at a time")

    async def embed_query(self, text: str) -> list[float] | None:
        if self._vectors is None:
            return None
        return self._vectors.get(text)


def _unused_responder() -> RecordingGroundedResponder:
    return RecordingGroundedResponder(
        body="unused",
        evidence_id=uuid.uuid4(),
        snapshot_id=None,
        source_title="unused",
        source_url="https://legacy.test/unused",
        cited_text="unused",
    )


async def _ask(session, site, text: str, responder=None) -> tuple[Conversation, Message]:
    visitor, conversation = await insert_bot_conversation(session, site)
    await session.commit()
    service = ConversationService(
        session, responder=responder or _unused_responder(), embedder=FakeEmbedder()
    )
    result = await service.visitor_message(
        conversation.id, visitor.id, HOST_ORIGIN, uuid.uuid4(), text
    )
    assert result.generation_id is not None
    await service.run_bot_turn(conversation.id, result.generation_id)
    reply = await session.scalar(
        select(Message)
        .where(Message.conversation_id == conversation.id, Message.role == "bot")
        .order_by(Message.id.desc())
        .limit(1)
    )
    assert reply is not None
    return conversation, reply


async def _hits(session) -> list[KnowledgeGapHit]:
    return list((await session.scalars(select(KnowledgeGapHit).order_by(KnowledgeGapHit.id))).all())


async def _pending_hit(session, site: Site, question: str) -> KnowledgeGapHit:
    visitor = Visitor(
        site_id=site.id, resume_token_hash=uuid.uuid4().hex, name="Ada Lopez", email="a@x.test"
    )
    session.add(visitor)
    await session.flush()
    conversation = Conversation(site_id=site.id, visitor_id=visitor.id, state="bot")
    session.add(conversation)
    await session.flush()
    reply = Message(
        conversation_id=conversation.id,
        site_id=site.id,
        role="bot",
        body="Could you rephrase that?",
        system_reason="clarify",
    )
    session.add(reply)
    await session.flush()
    hit = KnowledgeGapHit(
        site_id=site.id,
        conversation_id=conversation.id,
        message_id=reply.id,
        question=question,
        reason="no_evidence",
    )
    session.add(hit)
    await session.flush()
    return hit


async def _assign_all(session, embedder: StubEmbedder) -> int:
    assigned = 0
    while await KnowledgeGapService(session).assign_next(embedder):
        assigned += 1
    return assigned


async def test_unanswerable_question_leaves_one_pending_hit(migrated_db) -> None:
    """Catches a no-evidence miss never reaching the suggested-FAQ queue."""
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        conversation, reply = await _ask(session, site, ENROLL_PARAPHRASE)
        hits = await _hits(session)

    assert len(hits) == 1
    assert hits[0].question == ENROLL_PARAPHRASE
    assert hits[0].reason == "no_evidence"
    assert hits[0].site_id == site.id
    assert hits[0].conversation_id == conversation.id
    assert hits[0].message_id == reply.id
    assert hits[0].gap_id is None


async def test_rejected_model_answer_counts_as_a_miss(migrated_db) -> None:
    """Catches a grounding reject (the bot refused to guess) being invisible to the queue."""
    uncited_body = (
        "We provide DOT drug testing for small employers. "
        "A specialist can confirm details for your specific case."
    )

    class UncitedDraft:
        async def generate_grounded_draft(self, turn, documents, **_kwargs):
            del turn, documents
            return ModelDraft(body=uncited_body, citations=[], request_id="req_no_cite")

    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        await insert_chunk(
            session, site, "Do you provide DOT drug and alcohol testing?", ANSWER_VERBATIM
        )
        await _ask(
            session,
            site,
            "I have a company of 10 employees and I want drug testing for all of them",
            UncitedDraft(),
        )
        hits = await _hits(session)

    assert [hit.reason for hit in hits] == ["grounding_reject"]


async def test_a_database_error_while_recording_never_loses_the_reply(
    migrated_db, monkeypatch
) -> None:
    """Catches a constraint error in the gap table aborting the transaction that stores the reply."""
    real_add_hit = KnowledgeGapRepository.add_hit

    async def add_hit_for_a_missing_message(self, *, message_id: int, **kwargs) -> None:
        await real_add_hit(self, message_id=message_id + 1_000_000, **kwargs)

    monkeypatch.setattr(KnowledgeGapRepository, "add_hit", add_hit_for_a_missing_message)
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        conversation, _ = await _ask(session, site, ENROLL_PARAPHRASE)
    async with session_maker()() as session:
        stored = list(
            (
                await session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation.id, Message.role == "bot")
                    .order_by(Message.id)
                )
            ).all()
        )
        hits = await _hits(session)

    assert [(row.system_reason, row.response_reason_code) for row in stored] == [
        ("clarify", "no_evidence")
    ]
    assert hits == []


async def test_a_provider_outage_is_not_a_knowledge_gap(migrated_db) -> None:
    """Catches an Anthropic outage filling the queue with questions the site already answers."""

    class DownProvider:
        async def generate_grounded_draft(self, turn, documents, **_kwargs):
            del turn, documents
            raise TimeoutError

    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        await insert_chunk(
            session, site, "Do you provide DOT drug and alcohol testing?", ANSWER_VERBATIM
        )
        _, reply = await _ask(session, site, "Do you provide drug screening?", DownProvider())
        hits = await _hits(session)

    assert reply.response_reason_code == "tech_fail"
    assert hits == []


async def test_a_cited_answer_leaves_no_hit(migrated_db) -> None:
    """Catches every bot turn being recorded as a gap instead of only the misses."""
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        chunk = await insert_chunk(
            session, site, "Do you provide DOT drug and alcohol testing?", ANSWER_VERBATIM
        )
        page = await session.get(KbPage, chunk.page_id)
        assert page is not None
        responder = RecordingGroundedResponder(
            body="Yes. We handle DOT drug and alcohol testing.",
            evidence_id=chunk.id,
            snapshot_id=chunk.snapshot_id,
            source_title=page.title,
            source_url=page.url,
            cited_text=ANSWER_VERBATIM,
        )
        _, reply = await _ask(session, site, "Do you provide drug screening?", responder)
        hits = await _hits(session)

    assert reply.response_outcome == "synthesized_answer"
    assert hits == []


async def test_a_canned_answer_leaves_no_hit(migrated_db) -> None:
    """Catches a verbatim canned answer being counted as a knowledge gap."""
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        session.add(CannedReply(site_id=site.id, shortcut="turnaround_results", body=CANNED_BODY))
        _, reply = await _ask(session, site, "How long until results come back?")
        hits = await _hits(session)

    assert reply.system_reason == "canned"
    assert hits == []


async def test_stored_question_has_visitor_contact_details_redacted(migrated_db) -> None:
    """Catches an email typed into a question being copied into the staff queue."""
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        await _ask(session, site, "My email is ada@example.com, what is the enrollment process?")
        hits = await _hits(session)

    assert [hit.question for hit in hits] == [
        "My email is [REDACTED], what is the enrollment process?"
    ]


async def test_similar_questions_share_a_gap_and_a_different_one_does_not(migrated_db) -> None:
    """Catches paraphrases of one question being split into separate suggestions."""
    embedder = StubEmbedder({ENROLL: A, ENROLL_PARAPHRASE: B, PRICING: C})
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        first = await _pending_hit(session, site, ENROLL)
        second = await _pending_hit(session, site, ENROLL_PARAPHRASE)
        third = await _pending_hit(session, site, PRICING)
        await session.commit()

        assigned = await _assign_all(session, embedder)
        await session.refresh(first)
        await session.refresh(second)
        await session.refresh(third)
        gaps = list((await session.scalars(select(KnowledgeGap))).all())

    assert assigned == 3
    assert first.gap_id == second.gap_id
    assert third.gap_id != first.gap_id
    assert sorted(gap.question for gap in gaps) == [ENROLL, PRICING]


async def test_a_question_just_below_the_threshold_gets_its_own_gap(migrated_db) -> None:
    """Catches unrelated questions being merged because the threshold is too loose."""
    embedder = StubEmbedder({ENROLL: A, NEAR_MISS: D})
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        first = await _pending_hit(session, site, ENROLL)
        second = await _pending_hit(session, site, NEAR_MISS)
        await session.commit()

        await _assign_all(session, embedder)
        await session.refresh(first)
        await session.refresh(second)

    assert first.gap_id != second.gap_id


async def test_identical_questions_on_two_websites_never_share_a_gap(migrated_db) -> None:
    """Catches SampleSite visitors' questions leaking into a Sample Services suggestion."""
    embedder = StubEmbedder({ENROLL: A})
    async with session_maker()() as session:
        easy = await insert_site(session, "samplesite", "SampleSite")
        background = await insert_site(session, "backgroundchecks", "Sample Services")
        easy_hit = await _pending_hit(session, easy, ENROLL)
        background_hit = await _pending_hit(session, background, ENROLL)
        await session.commit()

        await _assign_all(session, embedder)
        await session.refresh(easy_hit)
        await session.refresh(background_hit)
        gaps = {gap.id: gap.site_id for gap in (await session.scalars(select(KnowledgeGap))).all()}

    assert easy_hit.gap_id != background_hit.gap_id
    assert gaps[easy_hit.gap_id] == easy.id
    assert gaps[background_hit.gap_id] == background.id


async def test_without_an_embedding_only_identical_text_merges(migrated_db) -> None:
    """Catches an embedding outage fragmenting repeats, or merging different questions."""
    embedder = StubEmbedder(None)
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        first = await _pending_hit(session, site, ENROLL)
        repeat = await _pending_hit(session, site, ENROLL.lower())
        other = await _pending_hit(session, site, PRICING)
        await session.commit()

        await _assign_all(session, embedder)
        await session.refresh(first)
        await session.refresh(repeat)
        await session.refresh(other)

    assert first.gap_id == repeat.gap_id
    assert other.gap_id != first.gap_id


async def test_background_worker_clusters_pending_hits(migrated_db, monkeypatch) -> None:
    """Catches the worker loop never calling the clustering step, so hits stay pending."""
    monkeypatch.setattr(durable_work, "default_embedder", lambda: StubEmbedder({ENROLL: A}))
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        hit_id = (await _pending_hit(session, site, ENROLL)).id
        await session.commit()

    assert await durable_work._assign_gap_hit() is True
    assert await durable_work._assign_gap_hit() is False

    async with session_maker()() as session:
        hit = await session.get(KnowledgeGapHit, hit_id)
        assert hit is not None
        gap = await session.get(KnowledgeGap, hit.gap_id)
    assert gap is not None
    assert gap.question == ENROLL
    assert gap.status == "open"


async def test_assigning_with_nothing_pending_does_nothing(migrated_db) -> None:
    """Catches the worker loop spinning on an empty queue."""
    async with session_maker()() as session:
        assert await KnowledgeGapService(session).assign_next(StubEmbedder({})) is False
