from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, distinct, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_gap import KnowledgeGap, KnowledgeGapHit
from app.models.message import Message

# Held while a hit is matched to a gap, so two workers cannot create twin gaps.
ASSIGNMENT_LOCK_KEY = 365_001_046

_GAP_COLUMNS = (
    KnowledgeGap.id,
    KnowledgeGap.site_id,
    KnowledgeGap.question,
    KnowledgeGap.note,
    KnowledgeGap.status,
    KnowledgeGap.resolved_at,
)


@dataclass(frozen=True)
class GapRow:
    id: UUID
    site_id: UUID
    question: str
    note: str | None
    status: str
    resolved_at: datetime | None
    conversations: int
    last_seen_at: datetime
    spiking: bool


class KnowledgeGapRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_hit(
        self,
        *,
        site_id: UUID,
        conversation_id: UUID,
        message_id: int,
        question: str,
        reason: str,
    ) -> None:
        self._session.add(
            KnowledgeGapHit(
                site_id=site_id,
                conversation_id=conversation_id,
                message_id=message_id,
                question=question,
                reason=reason,
            )
        )
        await self._session.flush()

    async def claim_pending_hit(self) -> KnowledgeGapHit | None:
        result = await self._session.execute(
            select(KnowledgeGapHit)
            .where(KnowledgeGapHit.gap_id.is_(None))
            .order_by(KnowledgeGapHit.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return result.scalar_one_or_none()

    async def lock_assignment(self) -> None:
        await self._session.execute(select(func.pg_advisory_xact_lock(ASSIGNMENT_LOCK_KEY)))

    async def gap_with_question(self, site_id: UUID, question: str) -> KnowledgeGap | None:
        result = await self._session.execute(
            select(KnowledgeGap)
            .where(
                KnowledgeGap.site_id == site_id,
                func.lower(KnowledgeGap.question) == question.casefold(),
            )
            .order_by(KnowledgeGap.created_at)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def nearest_gap(
        self, site_id: UUID, embedder_id: str, vector: list[float]
    ) -> tuple[KnowledgeGap, float] | None:
        distance = KnowledgeGap.embedding.cosine_distance(vector)
        result = await self._session.execute(
            select(KnowledgeGap, distance)
            .where(
                KnowledgeGap.site_id == site_id,
                KnowledgeGap.embedder_id == embedder_id,
                KnowledgeGap.embedding.is_not(None),
            )
            .order_by(distance, KnowledgeGap.id)
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None
        return row[0], 1.0 - float(row[1])

    async def add_gap(
        self, site_id: UUID, question: str, vector: list[float] | None, embedder_id: str
    ) -> KnowledgeGap:
        gap = KnowledgeGap(
            site_id=site_id,
            question=question,
            embedding=vector,
            embedder_id=embedder_id if vector is not None else None,
        )
        self._session.add(gap)
        await self._session.flush()
        return gap

    async def get(self, gap_id: UUID) -> KnowledgeGap | None:
        return await self._session.get(KnowledgeGap, gap_id)

    async def lock(self, gap_id: UUID) -> KnowledgeGap | None:
        return await self._session.scalar(
            select(KnowledgeGap)
            .where(KnowledgeGap.id == gap_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def open_gaps(
        self,
        *,
        since: datetime,
        minimum: int,
        spike_since: datetime,
        spike_minimum: int,
        site_id: UUID | None = None,
        gap_ids: list[UUID] | None = None,
    ) -> list[GapRow]:
        """Open gaps that repeated enough in the window, or are spiking right now."""
        conversations = func.count(distinct(KnowledgeGapHit.conversation_id))
        recent = func.count(distinct(KnowledgeGapHit.conversation_id)).filter(
            KnowledgeGapHit.created_at >= spike_since
        )
        last_seen = func.max(KnowledgeGapHit.created_at)
        spiking = recent >= spike_minimum
        statement = (
            select(*_GAP_COLUMNS, conversations, last_seen, spiking)
            .join(KnowledgeGapHit, KnowledgeGapHit.gap_id == KnowledgeGap.id)
            .where(KnowledgeGap.status == "open", KnowledgeGapHit.created_at >= since)
            .group_by(KnowledgeGap.id)
            .having(or_(conversations >= minimum, spiking))
            .order_by(spiking.desc(), conversations.desc(), last_seen.desc(), KnowledgeGap.id)
        )
        if site_id is not None:
            statement = statement.where(KnowledgeGap.site_id == site_id)
        if gap_ids is not None:
            statement = statement.where(KnowledgeGap.id.in_(gap_ids))
        result = await self._session.execute(statement)
        return [GapRow(*row) for row in result.all()]

    async def count_with_status(self, status: str) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(KnowledgeGap).where(KnowledgeGap.status == status)
        )
        return int(result.scalar_one())

    async def closed_gaps(
        self, *, statuses: tuple[str, ...], site_id: UUID | None = None
    ) -> list[GapRow]:
        """Answered or dismissed gaps with all-time counts, most recently handled first."""
        conversations = func.count(distinct(KnowledgeGapHit.conversation_id))
        last_seen = func.coalesce(func.max(KnowledgeGapHit.created_at), KnowledgeGap.created_at)
        statement = (
            select(*_GAP_COLUMNS, conversations, last_seen, false())
            .outerjoin(KnowledgeGapHit, KnowledgeGapHit.gap_id == KnowledgeGap.id)
            .where(KnowledgeGap.status.in_(statuses))
            .group_by(KnowledgeGap.id)
            .order_by(KnowledgeGap.resolved_at.desc().nulls_last(), KnowledgeGap.id)
        )
        if site_id is not None:
            statement = statement.where(KnowledgeGap.site_id == site_id)
        result = await self._session.execute(statement)
        return [GapRow(*row) for row in result.all()]

    async def gap_ids_for_conversation(self, conversation_id: UUID) -> list[UUID]:
        result = await self._session.execute(
            select(distinct(KnowledgeGapHit.gap_id)).where(
                KnowledgeGapHit.conversation_id == conversation_id,
                KnowledgeGapHit.gap_id.is_not(None),
            )
        )
        return list(result.scalars().all())

    async def recent_questions(
        self, gap_ids: list[UUID], since: datetime | None
    ) -> dict[UUID, list[str]]:
        statement = select(KnowledgeGapHit.gap_id, KnowledgeGapHit.question).where(
            KnowledgeGapHit.gap_id.in_(gap_ids)
        )
        if since is not None:
            statement = statement.where(KnowledgeGapHit.created_at >= since)
        result = await self._session.execute(
            statement.order_by(KnowledgeGapHit.created_at.desc(), KnowledgeGapHit.id.desc())
        )
        questions: dict[UUID, list[str]] = {gap_id: [] for gap_id in gap_ids}
        for gap_id, question in result.all():
            questions[gap_id].append(question)
        return questions

    async def specialist_replies(self, gap_id: UUID, limit: int) -> list[str]:
        """The longest specialist message after the miss in each chat, newest chat first."""
        result = await self._session.execute(
            select(Message.id, Message.body)
            .join(
                KnowledgeGapHit,
                and_(
                    KnowledgeGapHit.conversation_id == Message.conversation_id,
                    Message.id > KnowledgeGapHit.message_id,
                ),
            )
            .where(KnowledgeGapHit.gap_id == gap_id, Message.role == "agent")
            .distinct(Message.conversation_id)
            .order_by(Message.conversation_id, func.length(Message.body).desc(), Message.id.desc())
        )
        newest_first = sorted(result.all(), key=lambda row: row[0], reverse=True)
        return list(dict.fromkeys(body for _, body in newest_first))[:limit]
