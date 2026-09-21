from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource


def live_chunks_query(site_id: UUID) -> Select[tuple[KbChunk, KbPage]]:
    """One eligibility filter for retrieval and pre-commit citation checks."""
    return (
        select(KbChunk, KbPage)
        .join(KbPage, KbPage.id == KbChunk.page_id)
        .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
        .join(KbSource, KbSource.id == KbPage.source_id)
        .where(
            KbChunk.site_id == site_id,
            KbChunk.enabled.is_(True),
            KbPage.enabled.is_(True),
            KbSource.enabled.is_(True),
            KbSnapshot.state == "live",
        )
    )


class KbChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_enabled_for_site(self, site_id: UUID, chunk_id: UUID) -> KbChunk | None:
        result = await self._session.execute(
            live_chunks_query(site_id).with_only_columns(KbChunk).where(KbChunk.id == chunk_id)
        )
        return result.scalar_one_or_none()

    async def get_enabled_with_page(
        self, site_id: UUID, chunk_id: UUID
    ) -> tuple[KbChunk, KbPage] | None:
        result = await self._session.execute(
            live_chunks_query(site_id).where(KbChunk.id == chunk_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row[1]
