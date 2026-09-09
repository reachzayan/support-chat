from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canned_reply import CannedReply


class CannedReplyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, site_id: UUID, shortcut: str, body: str) -> CannedReply:
        reply = CannedReply(site_id=site_id, shortcut=shortcut, body=body)
        self._session.add(reply)
        await self._session.flush()
        return reply

    async def get_by_site_shortcut(self, site_id: UUID, shortcut: str) -> CannedReply | None:
        result = await self._session.execute(
            select(CannedReply).where(
                CannedReply.site_id == site_id,
                CannedReply.shortcut == shortcut,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_site(self, site_id: UUID) -> list[CannedReply]:
        result = await self._session.execute(
            select(CannedReply).where(CannedReply.site_id == site_id).order_by(CannedReply.shortcut)
        )
        return list(result.scalars().all())
