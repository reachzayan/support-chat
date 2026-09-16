from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_page_job import KbPageJob
from app.settings import get_settings


class KbPageJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, *, source_id: UUID, page_id: UUID, snapshot_id: UUID) -> KbPageJob:
        existing = await self._session.scalar(
            select(KbPageJob).where(
                KbPageJob.page_id == page_id, KbPageJob.snapshot_id == snapshot_id
            )
        )
        if existing is not None:
            return existing
        job = KbPageJob(
            source_id=source_id,
            page_id=page_id,
            snapshot_id=snapshot_id,
            stage="fetch",
            state="pending",
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def list_for_source(self, source_id: UUID) -> list[KbPageJob]:
        result = await self._session.execute(
            select(KbPageJob)
            .where(KbPageJob.source_id == source_id)
            .order_by(KbPageJob.created_at.desc(), KbPageJob.id)
        )
        return list(result.scalars().all())

    async def get_for_page_snapshot(self, page_id: UUID, snapshot_id: UUID) -> KbPageJob | None:
        return await self._session.scalar(
            select(KbPageJob).where(
                KbPageJob.page_id == page_id,
                KbPageJob.snapshot_id == snapshot_id,
            )
        )

    async def reap_stuck(self, now: datetime | None = None) -> int:
        settings = get_settings()
        stamp = now or datetime.now(UTC)
        cutoff = stamp - timedelta(minutes=settings.kb_ingest_stuck_minutes)
        result = await self._session.execute(
            select(KbPageJob)
            .where(KbPageJob.state == "running", KbPageJob.started_at < cutoff)
            .with_for_update(skip_locked=True)
        )
        rows = list(result.scalars().all())
        for job in rows:
            job.state = "pending"
            job.attempts = job.attempts + 1
            job.next_run_at = stamp
            job.last_error_code = "stuck"
        await self._session.flush()
        return len(rows)
