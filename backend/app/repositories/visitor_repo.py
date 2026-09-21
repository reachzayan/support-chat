from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.visitor import Visitor


class VisitorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        site_id: UUID,
        resume_token_hash: str,
        ip: str | None = None,
        user_agent: str | None = None,
        location: str | None = None,
    ) -> Visitor:
        visitor = Visitor(
            site_id=site_id,
            resume_token_hash=resume_token_hash,
            ip=ip,
            user_agent=user_agent,
            location=location,
        )
        self._session.add(visitor)
        await self._session.flush()
        return visitor

    async def get_by_id(self, visitor_id: UUID) -> Visitor | None:
        return await self._session.get(Visitor, visitor_id)

    async def lock_by_id(self, visitor_id: UUID) -> Visitor | None:
        result = await self._session.execute(
            select(Visitor).where(Visitor.id == visitor_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_resume_hash(self, site_id: UUID, resume_token_hash: str) -> Visitor | None:
        result = await self._session.execute(
            select(Visitor).where(
                Visitor.site_id == site_id,
                Visitor.resume_token_hash == resume_token_hash,
            )
        )
        return result.scalar_one_or_none()

    async def lock_by_resume_hash(self, site_id: UUID, resume_token_hash: str) -> Visitor | None:
        result = await self._session.execute(
            select(Visitor)
            .where(
                Visitor.site_id == site_id,
                Visitor.resume_token_hash == resume_token_hash,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()
