from datetime import UTC, datetime, timedelta

from sqlalchemy import Date, and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.status_sample import StatusSample

SAMPLE_RETENTION_DAYS = 90


class StatusSampleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, rows: list[tuple[str, bool, int | None]]) -> None:
        now = datetime.now(UTC)
        for service, ok, latency_ms in rows:
            self._session.add(
                StatusSample(service=service, ok=ok, latency_ms=latency_ms, created_at=now)
            )
        await self._session.flush()

    async def uptime_counts(
        self, now: datetime
    ) -> list[tuple[str, int, int, int, int, int, int, int, int]]:
        h24 = now - timedelta(hours=24)
        d7 = now - timedelta(days=7)
        d30 = now - timedelta(days=30)
        d90 = now - timedelta(days=90)
        created = StatusSample.created_at
        result = await self._session.execute(
            select(
                StatusSample.service,
                func.count().filter(created >= h24),
                func.count().filter(and_(created >= h24, StatusSample.ok.is_(True))),
                func.count().filter(created >= d7),
                func.count().filter(and_(created >= d7, StatusSample.ok.is_(True))),
                func.count().filter(created >= d30),
                func.count().filter(and_(created >= d30, StatusSample.ok.is_(True))),
                func.count().filter(created >= d90),
                func.count().filter(and_(created >= d90, StatusSample.ok.is_(True))),
            )
            .where(created >= d90)
            .group_by(StatusSample.service)
        )
        return list(result.all())

    async def availability_days(self, start: datetime) -> list[tuple[str, object, bool]]:
        utc_ts = func.timezone("UTC", StatusSample.created_at)
        day = func.cast(utc_ts, Date)
        result = await self._session.execute(
            select(StatusSample.service, day, func.bool_and(StatusSample.ok))
            .where(StatusSample.created_at >= start)
            .group_by(StatusSample.service, day)
        )
        return list(result.all())

    async def hourly_medians(self, start: datetime) -> list[tuple[str, datetime, float]]:
        hour = func.date_trunc("hour", func.timezone("UTC", StatusSample.created_at))
        median = func.percentile_cont(0.5).within_group(StatusSample.latency_ms)
        result = await self._session.execute(
            select(StatusSample.service, hour, median)
            .where(
                StatusSample.created_at >= start,
                StatusSample.latency_ms.is_not(None),
            )
            .group_by(StatusSample.service, hour)
        )
        return [(row[0], row[1], float(row[2])) for row in result.all()]

    async def down_services_by_day(self, start: datetime) -> list[tuple[object, str]]:
        utc_ts = func.timezone("UTC", StatusSample.created_at)
        day = func.cast(utc_ts, Date)
        result = await self._session.execute(
            select(day, StatusSample.service)
            .where(StatusSample.created_at >= start, StatusSample.ok.is_(False))
            .group_by(day, StatusSample.service)
        )
        return list(result.all())

    async def delete_older_than(self, cutoff: datetime) -> int:
        result = await self._session.execute(
            delete(StatusSample).where(StatusSample.created_at < cutoff)
        )
        return int(result.rowcount or 0)
