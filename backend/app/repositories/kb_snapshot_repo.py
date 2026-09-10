from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_snapshot import KbSnapshot


class KbSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_source(self, source_id: UUID) -> list[KbSnapshot]:
        result = await self._session.execute(
            select(KbSnapshot)
            .where(KbSnapshot.source_id == source_id)
            .order_by(KbSnapshot.created_at.desc(), KbSnapshot.id.desc())
        )
        return list(result.scalars().all())

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
