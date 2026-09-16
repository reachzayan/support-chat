from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canned_reply import CannedReply


class CannedReplyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, site_id: UUID | None, shortcut: str, body: str, enabled: bool
    ) -> CannedReply:
        reply = CannedReply(site_id=site_id, shortcut=shortcut, body=body, enabled=enabled)
        self._session.add(reply)
        await self._session.flush()
        return reply

    async def get_by_id(self, reply_id: UUID) -> CannedReply | None:
        return await self._session.get(CannedReply, reply_id)

    async def get_by_scope_shortcut(
        self, site_id: UUID | None, shortcut: str, *, exclude_id: UUID | None = None
    ) -> CannedReply | None:
        conditions = [func.lower(CannedReply.shortcut) == shortcut]
        if site_id is None:
            conditions.append(CannedReply.site_id.is_(None))
        else:
            conditions.append(CannedReply.site_id == site_id)
        if exclude_id is not None:
            conditions.append(CannedReply.id != exclude_id)
        result = await self._session.execute(select(CannedReply).where(*conditions))
        return result.scalar_one_or_none()

    async def list_library(self) -> list[CannedReply]:
        result = await self._session.execute(
            select(CannedReply).order_by(
                CannedReply.site_id.is_not(None),
                CannedReply.site_id,
                CannedReply.shortcut,
                CannedReply.id,
            )
        )
        return list(result.scalars().all())

    async def list_general_and_site(self, site_id: UUID) -> list[CannedReply]:
        result = await self._session.execute(
            select(CannedReply)
            .where(CannedReply.site_id.is_(None) | (CannedReply.site_id == site_id))
            .order_by(CannedReply.shortcut, CannedReply.id)
        )
        return list(result.scalars().all())

    async def delete(self, reply: CannedReply) -> None:
        await self._session.delete(reply)
