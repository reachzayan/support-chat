from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_log import AppLog

DEFAULT_RETENTION_DAYS = 7


class AppLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, log_id: UUID) -> AppLog | None:
        return await self._session.get(AppLog, log_id)

    async def add(self, row: AppLog) -> AppLog:
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_recent(
        self,
        *,
        since: datetime | None = None,
        level: str | None = None,
        source: str | None = None,
        limit: int = 500,
    ) -> list[AppLog]:
        cutoff = since or (datetime.now(UTC) - timedelta(days=DEFAULT_RETENTION_DAYS))
        stmt = select(AppLog).where(AppLog.created_at >= cutoff)
        if level:
            stmt = stmt.where(AppLog.level == level)
        if source:
            stmt = stmt.where(AppLog.source == source)
        stmt = stmt.order_by(AppLog.created_at.desc()).limit(min(max(limit, 1), 2000))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_level_since(self, *, level: str, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(AppLog)
            .where(AppLog.level == level, AppLog.created_at >= since)
        )
        return int(result.scalar_one())
