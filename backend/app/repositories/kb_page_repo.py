from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage


class KbPageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_source(self, source_id: UUID) -> list[KbPage]:
        result = await self._session.execute(
            select(KbPage).where(KbPage.source_id == source_id).order_by(KbPage.url)
        )
        return list(result.scalars().all())

    async def get_by_id(self, page_id: UUID) -> KbPage | None:
        return await self._session.get(KbPage, page_id)

    async def get_for_source_url(self, source_id: UUID, url: str) -> KbPage | None:
        result = await self._session.execute(
            select(KbPage).where(KbPage.source_id == source_id, KbPage.url == url)
        )
        return result.scalar_one_or_none()

    async def delete_chunks(self, page_id: UUID) -> None:
        await self._session.execute(delete(KbChunk).where(KbChunk.page_id == page_id))

    async def delete_urls_not_in(self, source_id: UUID, keep_urls: set[str]) -> None:
        query = delete(KbPage).where(KbPage.source_id == source_id)
        if keep_urls:
            query = query.where(KbPage.url.notin_(list(keep_urls)))
        await self._session.execute(query)
