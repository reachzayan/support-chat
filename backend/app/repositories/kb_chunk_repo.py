from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource


class KbChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_enabled_for_site(self, site_id: UUID, chunk_id: UUID) -> KbChunk | None:
        result = await self._session.execute(
            select(KbChunk)
            .join(KbPage, KbPage.id == KbChunk.page_id)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .join(KbSource, KbSource.id == KbPage.source_id)
            .where(
                KbChunk.id == chunk_id,
                KbChunk.site_id == site_id,
                KbChunk.enabled.is_(True),
                KbPage.enabled.is_(True),
                KbSource.enabled.is_(True),
                KbSnapshot.state == "live",
            )
        )
        return result.scalar_one_or_none()

    async def get_enabled_with_page(
        self, site_id: UUID, chunk_id: UUID
    ) -> tuple[KbChunk, KbPage] | None:
        result = await self._session.execute(
            select(KbChunk, KbPage)
            .join(KbPage, KbPage.id == KbChunk.page_id)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .join(KbSource, KbSource.id == KbPage.source_id)
            .where(
                KbChunk.id == chunk_id,
                KbChunk.site_id == site_id,
                KbChunk.enabled.is_(True),
                KbPage.enabled.is_(True),
                KbSource.enabled.is_(True),
                KbSnapshot.state == "live",
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row[1]
