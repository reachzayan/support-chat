"""Suggested FAQs: repeated questions the assistant could not answer.

A bot miss is stored as a hit (redacted question, no transcript copy). A background step
clusters hits into one gap per repeated question. A gap reaches the staff queue only after
it stumped the bot in several different chats within the window, and it is never published
without a staff member writing the answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.knowledge_gap import KnowledgeGap
from app.models.message import Message
from app.models.user import User
from app.repositories.knowledge_gap_repo import KnowledgeGapRepository
from app.repositories.message_repo import MessageRepository
from app.services.grounded_response_types import ResponseDecision
from app.services.kb_embedder import Embedder
from app.services.pii_redactor import redact_for_model
from app.settings import get_settings

log = structlog.get_logger("knowledge_gap")

# Decisions where the visitor's question had no verified answer on the site. A provider
# outage (tech_fail) is not a content gap, and canned answers are answers.
GAP_REASONS = frozenset({"no_evidence", "grounding_reject", "repeated_miss", "needs_confirmation"})
EXAMPLE_LIMIT = 3
REPLY_LIMIT = 3


@dataclass
class KnowledgeGapError(Exception):
    code: str


# The views a staff member can open. "answered" covers both ways of answering.
VIEW_STATUSES = {"answered": ("canned", "knowledge"), "dismissed": ("dismissed",)}
NOTE_MAX = 1000


@dataclass(frozen=True)
class QueueItem:
    id: UUID
    site_id: UUID
    question: str
    conversations: int
    last_seen_at: datetime
    examples: list[str]
    spiking: bool
    note: str | None
    status: str
    resolved_at: datetime | None


@dataclass(frozen=True)
class Queue:
    items: list[QueueItem]
    min_conversations: int
    window_days: int
    spike_conversations: int
    spike_hours: int


class KnowledgeGapService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._gaps = KnowledgeGapRepository(session)

    async def record_miss(
        self, conversation: Conversation, reply: Message, decision: ResponseDecision
    ) -> None:
        """Called in the transaction that stores the bot's reply; it must never break it.

        A savepoint keeps a database error here from aborting the visitor's reply. The log
        names only the error class: SQL errors carry the question text as a parameter.
        """
        if decision.reason_code not in GAP_REASONS:
            return
        try:
            async with self._session.begin_nested():
                await self._store_hit(conversation, reply, decision.reason_code)
        except Exception as exc:
            log.warning(
                "knowledge_gap_record_failed",
                conversation_id=str(conversation.id),
                error_class=type(exc).__name__,
            )

    async def _store_hit(self, conversation: Conversation, reply: Message, reason: str) -> None:
        visitor_text = await MessageRepository(self._session).latest_visitor_body(conversation.id)
        question = redact_for_model(visitor_text).strip()
        if not question:
            return
        await self._gaps.add_hit(
            site_id=conversation.site_id,
            conversation_id=conversation.id,
            message_id=reply.id,
            question=question,
            reason=reason,
        )

    async def assign_next(self, embedder: Embedder) -> bool:
        """Cluster one pending hit. Returns False when nothing was waiting."""
        hit = await self._gaps.claim_pending_hit()
        if hit is None:
            await self._session.commit()
            return False
        vector = await _question_vector(embedder, hit.question)
        await self._gaps.lock_assignment()
        gap = await self._matching_gap(hit.site_id, hit.question, embedder.embedder_id, vector)
        if gap is None:
            gap = await self._gaps.add_gap(hit.site_id, hit.question, vector, embedder.embedder_id)
        hit.gap_id = gap.id
        await self._session.commit()
        return True

    async def queue(self, site_id: UUID | None, view: str = "open") -> Queue:
        settings = get_settings()
        now = datetime.now(UTC)
        since = now - timedelta(days=settings.knowledge_gap_window_days)
        if view == "open":
            rows = await self._gaps.open_gaps(
                since=since,
                minimum=settings.knowledge_gap_min_conversations,
                spike_since=now - timedelta(hours=settings.knowledge_gap_spike_hours),
                spike_minimum=settings.knowledge_gap_spike_conversations,
                site_id=site_id,
            )
        else:
            rows = await self._gaps.closed_gaps(statuses=VIEW_STATUSES[view], site_id=site_id)
        # History keeps every phrasing ever seen; the live queue only the current window.
        asked = await self._gaps.recent_questions(
            [row.id for row in rows], since if view == "open" else None
        )
        return Queue(
            items=[
                QueueItem(
                    id=row.id,
                    site_id=row.site_id,
                    question=row.question,
                    conversations=row.conversations,
                    last_seen_at=row.last_seen_at,
                    examples=_examples(row.question, asked[row.id]),
                    spiking=row.spiking,
                    note=row.note,
                    status=row.status,
                    resolved_at=row.resolved_at,
                )
                for row in rows
            ],
            min_conversations=settings.knowledge_gap_min_conversations,
            window_days=settings.knowledge_gap_window_days,
            spike_conversations=settings.knowledge_gap_spike_conversations,
            spike_hours=settings.knowledge_gap_spike_hours,
        )

    async def for_conversation(self, conversation_id: UUID) -> QueueItem | None:
        """The listed question this chat is part of, for the inbox badge."""
        gap_ids = await self._gaps.gap_ids_for_conversation(conversation_id)
        if not gap_ids:
            return None
        settings = get_settings()
        now = datetime.now(UTC)
        rows = await self._gaps.open_gaps(
            since=now - timedelta(days=settings.knowledge_gap_window_days),
            minimum=settings.knowledge_gap_min_conversations,
            spike_since=now - timedelta(hours=settings.knowledge_gap_spike_hours),
            spike_minimum=settings.knowledge_gap_spike_conversations,
            gap_ids=gap_ids,
        )
        if not rows:
            return None
        row = rows[0]
        return QueueItem(
            id=row.id,
            site_id=row.site_id,
            question=row.question,
            conversations=row.conversations,
            last_seen_at=row.last_seen_at,
            examples=[],
            spiking=row.spiking,
            note=row.note,
            status=row.status,
            resolved_at=row.resolved_at,
        )

    async def reopen(self, gap_id: UUID) -> None:
        gap = await self._gaps.get(gap_id)
        if gap is None:
            raise KnowledgeGapError("not_found")
        if gap.status == "open":
            raise KnowledgeGapError("already_open")
        gap.status = "open"
        gap.resolved_by = None
        gap.resolved_at = None
        await self._session.commit()

    async def set_note(self, gap_id: UUID, note: str | None) -> None:
        gap = await self._gaps.get(gap_id)
        if gap is None:
            raise KnowledgeGapError("not_found")
        gap.note = (note or "").strip()[:NOTE_MAX] or None
        await self._session.commit()

    async def get_gap(self, gap_id: UUID) -> KnowledgeGap | None:
        return await self._gaps.get(gap_id)

    async def specialist_replies(self, gap_id: UUID) -> list[str]:
        gap = await self._gaps.get(gap_id)
        if gap is None:
            raise KnowledgeGapError("not_found")
        return await self._gaps.specialist_replies(gap_id, REPLY_LIMIT)

    async def dismiss(self, gap_id: UUID, user: User) -> None:
        await self.close(await self.open_gap(gap_id), "dismissed", user)

    async def open_gap(self, gap_id: UUID) -> KnowledgeGap:
        gap = await self._gaps.get(gap_id)
        if gap is None:
            raise KnowledgeGapError("not_found")
        if gap.status != "open":
            raise KnowledgeGapError("not_open")
        return gap

    async def close(self, gap: KnowledgeGap, status: str, user: User) -> None:
        gap.status = status
        gap.resolved_by = user.id
        gap.resolved_at = datetime.now(UTC)
        await self._session.commit()

    async def _matching_gap(
        self, site_id: UUID, question: str, embedder_id: str, vector: list[float] | None
    ) -> KnowledgeGap | None:
        same_words = await self._gaps.gap_with_question(site_id, question)
        if same_words is not None or vector is None:
            return same_words
        nearest = await self._gaps.nearest_gap(site_id, embedder_id, vector)
        if nearest is None:
            return None
        gap, similarity = nearest
        return gap if similarity >= get_settings().knowledge_gap_similarity else None


async def _question_vector(embedder: Embedder, question: str) -> list[float] | None:
    try:
        return await embedder.embed_query(question)
    except Exception:
        log.info("knowledge_gap_embed_failed")
        return None


def _examples(representative: str, asked_newest_first: list[str]) -> list[str]:
    """Other ways visitors phrased the question, without repeating the card title."""
    seen = {representative.casefold()}
    examples: list[str] = []
    for question in asked_newest_first:
        if question.casefold() in seen:
            continue
        seen.add(question.casefold())
        examples.append(question)
    return examples[:EXAMPLE_LIMIT]
