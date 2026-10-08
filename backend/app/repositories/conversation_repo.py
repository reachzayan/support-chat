from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.state_machine import apply_event
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.site import Site
from app.models.user import User
from app.models.visitor import Visitor
from app.models.visitor_block import VisitorBlock


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
                or_(
                    Conversation.state != "queued",
                    Conversation.site_id.in_(select(Site.id).where(Site.human_enabled)),
                ),
                or_(
                    Conversation.last_message_at <= cutoff,
                    Conversation.handoff_wait_started_at <= cutoff,
                ),
                Conversation.handoff_wait_prompt_id.is_(None),
                Conversation.active_generation_id.is_(None),
            )
            .order_by(Conversation.last_message_at, Conversation.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def claim_generation(
        self, conversation_id: UUID, generation_id: UUID, *, lease: timedelta
    ) -> bool:
        now = datetime.now(UTC)
        conversation = await self.lock_by_id(conversation_id)
        if (
            conversation is None
            or conversation.state != "bot"
            or conversation.active_generation_id != generation_id
            or (
                conversation.generation_lease_expires_at is not None
                and conversation.generation_lease_expires_at > now
            )
        ):
            await self._session.commit()
            return False
        conversation.generation_created_at = conversation.generation_created_at or now
        conversation.generation_lease_expires_at = now + lease
        await self._session.commit()
        return True

    async def claim_recoverable_generation(
        self, *, recovery_grace: timedelta, lease: timedelta
    ) -> tuple[UUID, UUID] | None:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(Conversation)
            .where(
                Conversation.state == "bot",
                Conversation.active_generation_id.is_not(None),
                or_(
                    Conversation.generation_lease_expires_at <= now,
                    and_(
                        Conversation.generation_lease_expires_at.is_(None),
                        Conversation.generation_created_at <= now - recovery_grace,
                    ),
                ),
            )
            .order_by(Conversation.generation_created_at, Conversation.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None or conversation.active_generation_id is None:
            await self._session.commit()
            return None
        generation_id = conversation.active_generation_id
        conversation.generation_lease_expires_at = now + lease
        await self._session.commit()
        return conversation.id, generation_id

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
    ) -> list[tuple[Conversation, User | None, str | None]]:
        opening_message = (
            select(func.left(Message.body, 180))
            .where(Message.conversation_id == Conversation.id, Message.role == "visitor")
            .order_by(Message.id)
            .limit(1)
            .correlate(Conversation)
            .scalar_subquery()
        )
        result = await self._session.execute(
            select(Conversation, User, opening_message)
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
        return [(conversation, agent, preview) for conversation, agent, preview in result.all()]

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
        site_id: UUID | None = None,
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
        if site_id is not None:
            query = query.where(Conversation.site_id == site_id)
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

    async def count_inbox_by_state(self, site_id: UUID | None = None) -> dict[str, int]:
        counts = {"bot": 0, "queued": 0, "human": 0, "closed": 0}
        query = select(Conversation.state, func.count()).where(
            Conversation.state.in_(("bot", "queued", "human", "closed"))
        )
        if site_id is not None:
            query = query.where(Conversation.site_id == site_id)
        result = await self._session.execute(query.group_by(Conversation.state))
        for state, total in result.all():
            counts[str(state)] = int(total)
        return counts

    async def count_closed_since(self, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.state == "closed", Conversation.closed_at >= since)
        )
        return int(result.scalar_one())

    async def list_inbox_sites(self) -> list[tuple[Site, int]]:
        queued = func.coalesce(
            func.sum(case((Conversation.state == "queued", 1), else_=0)),
            0,
        )
        result = await self._session.execute(
            select(Site, queued)
            .outerjoin(Conversation, Conversation.site_id == Site.id)
            .group_by(Site.id)
            .order_by(Site.name, Site.id)
        )
        return [(site, int(total)) for site, total in result.all()]

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

    async def list_open_matching_identifiers(
        self,
        site_id: UUID,
        *,
        ip: str | None,
        email: str | None,
        phone: str | None,
    ) -> list[Conversation]:
        matches = []
        if ip:
            matches.append(Visitor.ip == ip)
        if email:
            matches.append(Visitor.email == email)
        if phone:
            matches.append(Visitor.phone == phone)
        if not matches:
            return []
        result = await self._session.execute(
            select(Conversation)
            .join(Visitor, Visitor.id == Conversation.visitor_id)
            .where(
                Conversation.site_id == site_id,
                Conversation.state != "closed",
                or_(*matches),
            )
            .with_for_update()
        )
        return list(result.scalars().all())

    async def list_submissions(
        self,
        *,
        offset: int,
        limit: int,
        site_id: UUID | None = None,
        conversation_id: UUID | None = None,
        created_from: datetime | None = None,
        created_before: datetime | None = None,
    ) -> list[tuple[Conversation, Visitor, Site, User | None, str | None, UUID | None]]:
        opening_body = (
            select(Message.body)
            .where(Message.conversation_id == Conversation.id, Message.role == "visitor")
            .order_by(Message.id.asc())
            .limit(1)
            .scalar_subquery()
        )
        block_id = (
            select(VisitorBlock.id)
            .where(
                VisitorBlock.site_id == Conversation.site_id,
                or_(
                    and_(
                        VisitorBlock.email.is_not(None),
                        VisitorBlock.email == func.lower(Visitor.email),
                    ),
                    and_(VisitorBlock.phone.is_not(None), VisitorBlock.phone == Visitor.phone),
                    and_(VisitorBlock.ip.is_not(None), VisitorBlock.ip == Visitor.ip),
                ),
            )
            .order_by(VisitorBlock.created_at.desc(), VisitorBlock.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        query = (
            select(Conversation, Visitor, Site, User, opening_body, block_id)
            .join(Visitor, Visitor.id == Conversation.visitor_id)
            .join(Site, Site.id == Conversation.site_id)
            .outerjoin(User, User.id == Conversation.assigned_agent_id)
            .where(Conversation.prechat_submission_id.is_not(None))
        )
        if conversation_id is not None:
            query = query.where(Conversation.id == conversation_id)
        if site_id is not None:
            query = query.where(Conversation.site_id == site_id)
        if created_from is not None:
            query = query.where(Conversation.created_at >= created_from)
        if created_before is not None:
            query = query.where(Conversation.created_at < created_before)
        query = (
            query.order_by(Conversation.last_message_at.desc(), Conversation.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(query)
        return [
            (conversation, visitor, site, agent, opening, matched_block_id)
            for conversation, visitor, site, agent, opening, matched_block_id in result.all()
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
