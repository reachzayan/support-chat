from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_source import KbSource

STUCK_AFTER = timedelta(minutes=20)


class KbSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_site(self, site_id: UUID) -> list[KbSource]:
        result = await self._session.execute(
            select(KbSource).where(KbSource.site_id == site_id).order_by(KbSource.created_at)
        )
        return list(result.scalars().all())

    async def get_by_id(self, source_id: UUID) -> KbSource | None:
        return await self._session.get(KbSource, source_id)

    async def get_by_site_start_url(self, site_id: UUID, start_url: str) -> KbSource | None:
        result = await self._session.execute(
            select(KbSource).where(KbSource.site_id == site_id, KbSource.start_url == start_url)
        )
        return result.scalar_one_or_none()

    async def lock_by_id(self, source_id: UUID) -> KbSource | None:
        result = await self._session.execute(
            select(KbSource)
            .where(KbSource.id == source_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def claim_next(self, hinted_id: UUID | None = None) -> KbSource | None:
        due = or_(
            KbSource.status == "queued",
            and_(
                KbSource.status == "running",
                KbSource.updated_at < datetime.now(UTC) - STUCK_AFTER,
            ),
        )
        if hinted_id is not None:
            hinted = await self._session.execute(
                select(KbSource)
                .where(KbSource.id == hinted_id, due)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
            source = hinted.scalar_one_or_none()
            if source is not None:
                return await self._mark_running(source)
        result = await self._session.execute(
            select(KbSource)
            .where(due)
            .order_by(KbSource.updated_at, KbSource.id)
            .with_for_update(skip_locked=True)
            .limit(1)
            .execution_options(populate_existing=True)
        )
        source = result.scalar_one_or_none()
        if source is None:
            return None
        return await self._mark_running(source)

    async def _mark_running(self, source: KbSource) -> KbSource:
        source.status = "running"
        source.error_code = None
        await self._session.commit()
        await self._session.refresh(source)
        return source
