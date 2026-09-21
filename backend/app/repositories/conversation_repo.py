from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.state_machine import apply_event
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.site import Site
from app.models.user import User
from app.models.visitor import Visitor


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, site_id: UUID, visitor_id: UUID, state: str) -> Conversation:
        conversation = Conversation(site_id=site_id, visitor_id=visitor_id, state=state)
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        return await self._session.get(Conversation, conversation_id)

    async def lock_by_id(self, conversation_id: UUID) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_expired_open(self, cutoff: datetime, *, limit: int = 100) -> list[Conversation]:
        result = await self._session.execute(
            select(Conversation)
            .where(
                Conversation.state.in_(("prechat", "bot", "queued", "human")),
                Conversation.last_message_at <= cutoff,
                Conversation.active_generation_id.is_(None),
            )
            .order_by(Conversation.last_message_at, Conversation.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def get_open_for_visitor(
        self, site_id: UUID, visitor_id: UUID, *, for_update: bool = False
    ) -> Conversation | None:
        query = select(Conversation).where(
            Conversation.site_id == site_id,
            Conversation.visitor_id == visitor_id,
            Conversation.state != "closed",
        )
        if for_update:
            query = query.with_for_update()
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def lock_for_visitor(
        self, site_id: UUID, visitor_id: UUID, conversation_id: UUID
    ) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.site_id == site_id,
                Conversation.visitor_id == visitor_id,
                Conversation.prechat_submission_id.is_not(None),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_for_visitor_history(
        self, site_id: UUID, visitor_id: UUID, *, limit: int
    ) -> list[tuple[Conversation, User | None]]:
        result = await self._session.execute(
            select(Conversation, User)
            .outerjoin(User, User.id == Conversation.assigned_agent_id)
            .where(
                Conversation.site_id == site_id,
                Conversation.visitor_id == visitor_id,
                Conversation.prechat_submission_id.is_not(None),
            )
            .order_by(
                (Conversation.state != "closed").desc(),
                Conversation.last_message_at.desc(),
                Conversation.id.desc(),
            )
            .limit(limit)
        )
        return [(conversation, agent) for conversation, agent in result.all()]

    async def count_for_visitor_history(self, site_id: UUID, visitor_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Conversation)
            .where(
                Conversation.site_id == site_id,
                Conversation.visitor_id == visitor_id,
                Conversation.prechat_submission_id.is_not(None),
            )
        )
        return int(result.scalar_one())

    async def list_inbox(
        self,
        *,
        state: str | None,
        cursor_ts: datetime | None,
        cursor_id: UUID | None,
        limit: int,
    ) -> list[tuple[Conversation, Visitor, Site, User | None, str | None]]:
        latest_body = (
            select(Message.body)
            .where(Message.conversation_id == Conversation.id)
            .order_by(Message.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        query = (
            select(Conversation, Visitor, Site, User, latest_body)
            .join(Visitor, Visitor.id == Conversation.visitor_id)
            .join(Site, Site.id == Conversation.site_id)
            .outerjoin(User, User.id == Conversation.assigned_agent_id)
        )
        if state is not None:
            query = query.where(Conversation.state == state)
        if cursor_ts is not None and cursor_id is not None:
            query = query.where(
                tuple_(Conversation.last_message_at, Conversation.id) < (cursor_ts, cursor_id)
            )
        query = query.order_by(Conversation.last_message_at.desc(), Conversation.id.desc()).limit(
            limit
        )
        result = await self._session.execute(query)
        return [
            (conversation, visitor, site, agent, preview)
            for conversation, visitor, site, agent, preview in result.all()
        ]

    async def count_inbox_by_state(self) -> dict[str, int]:
        counts = {"bot": 0, "queued": 0, "human": 0, "closed": 0}
        result = await self._session.execute(
            select(Conversation.state, func.count())
            .where(Conversation.state.in_(("bot", "queued", "human", "closed")))
            .group_by(Conversation.state)
        )
        for state, total in result.all():
            counts[str(state)] = int(total)
        return counts

    async def close_queued_for_site(self, site_id: UUID) -> list[Conversation]:
        result = await self._session.execute(
            select(Conversation)
            .where(Conversation.site_id == site_id, Conversation.state == "queued")
            .with_for_update()
        )
        rows = list(result.scalars().all())
        now = datetime.now(UTC)
        for conversation in rows:
            conversation.state = apply_event(conversation.state, "end")
            conversation.closed_at = now
            conversation.active_generation_id = None
        return rows

    async def list_submissions(
        self, *, limit: int
    ) -> list[tuple[Conversation, Visitor, Site, User | None, str | None]]:
        opening_body = (
            select(Message.body)
            .where(Message.conversation_id == Conversation.id, Message.role == "visitor")
            .order_by(Message.id.asc())
            .limit(1)
            .scalar_subquery()
        )
        query = (
            select(Conversation, Visitor, Site, User, opening_body)
            .join(Visitor, Visitor.id == Conversation.visitor_id)
            .join(Site, Site.id == Conversation.site_id)
            .outerjoin(User, User.id == Conversation.assigned_agent_id)
            .where(Conversation.prechat_submission_id.is_not(None))
            .order_by(Conversation.last_message_at.desc(), Conversation.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(query)
        return [
            (conversation, visitor, site, agent, opening)
            for conversation, visitor, site, agent, opening in result.all()
        ]

    async def get_inbox_detail(
        self, conversation_id: UUID
    ) -> tuple[Conversation, Visitor, Site, User | None] | None:
        query = (
            select(Conversation, Visitor, Site, User)
            .join(Visitor, Visitor.id == Conversation.visitor_id)
            .join(Site, Site.id == Conversation.site_id)
            .outerjoin(User, User.id == Conversation.assigned_agent_id)
            .where(Conversation.id == conversation_id)
        )
        result = await self._session.execute(query)
        row = result.one_or_none()
        if row is None:
            return None
        conversation, visitor, site, agent = row
        return conversation, visitor, site, agent
