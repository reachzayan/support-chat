from uuid import UUID

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_snapshot import KbSnapshot


class KbSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_source(self, source_id: UUID, *, limit: int = 50) -> list[KbSnapshot]:
        result = await self._session.execute(
            select(KbSnapshot)
            .where(KbSnapshot.source_id == source_id)
            .order_by(KbSnapshot.created_at.desc(), KbSnapshot.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def latest_for_source(self, source_id: UUID) -> KbSnapshot | None:
        result = await self._session.execute(
            select(KbSnapshot)
            .where(KbSnapshot.source_id == source_id)
            .order_by(KbSnapshot.created_at.desc(), KbSnapshot.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def status_for_source(self, source_id: UUID) -> KbSnapshot | None:
        priority = case(
            (KbSnapshot.state == "building", 0),
            (KbSnapshot.state == "validated", 1),
            (KbSnapshot.state == "live", 2),
            else_=3,
        )
        result = await self._session.execute(
            select(KbSnapshot)
            .where(KbSnapshot.source_id == source_id)
            .order_by(priority, KbSnapshot.created_at.desc(), KbSnapshot.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def summaries_for_sources(
        self, source_ids: list[UUID]
    ) -> dict[UUID, tuple[KbSnapshot | None, KbSnapshot | None]]:
        if not source_ids:
            return {}
        latest_ids = (
            select(KbSnapshot.id)
            .where(KbSnapshot.source_id.in_(source_ids))
            .distinct(KbSnapshot.source_id)
            .order_by(KbSnapshot.source_id, KbSnapshot.created_at.desc(), KbSnapshot.id.desc())
        )
        result = await self._session.execute(
            select(KbSnapshot)
            .where(
                KbSnapshot.source_id.in_(source_ids),
                or_(KbSnapshot.id.in_(latest_ids), KbSnapshot.state == "live"),
            )
            .order_by(KbSnapshot.source_id, KbSnapshot.created_at.desc(), KbSnapshot.id.desc())
            .limit(len(source_ids) * 2)
        )
        summaries: dict[UUID, tuple[KbSnapshot | None, KbSnapshot | None]] = {}
        for snapshot in result.scalars().all():
            latest, live = summaries.get(snapshot.source_id, (None, None))
            if latest is None:
                latest = snapshot
            if snapshot.state == "live":
                live = snapshot
            summaries[snapshot.source_id] = (latest, live)
        return summaries

    async def get_live(self, source_id: UUID) -> KbSnapshot | None:
        result = await self._session.execute(
            select(KbSnapshot).where(KbSnapshot.source_id == source_id, KbSnapshot.state == "live")
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, snapshot_id: UUID) -> KbSnapshot | None:
        return await self._session.get(KbSnapshot, snapshot_id)

    async def previous_superseded(self, source_id: UUID) -> KbSnapshot | None:
        result = await self._session.execute(
            select(KbSnapshot)
            .where(KbSnapshot.source_id == source_id, KbSnapshot.state == "superseded")
            .order_by(KbSnapshot.promoted_at.desc().nullslast(), KbSnapshot.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
