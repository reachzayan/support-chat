"""Historical uptime, availability bars, latency, and incident days."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.status_sample_repo import StatusSampleRepository

MONITORS = (
    ("api", "API"),
    ("postgres", "Postgres"),
    ("redis", "Redis"),
    ("worker", "Background work"),
)


def _pct(ok: int, total: int) -> float | None:
    if total == 0:
        return None
    return round(ok * 1000 / total) / 10


def _worst(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return min(present)


def _incident_summary(names: list[str]) -> str:
    if not names:
        return "No incidents"
    if len(names) == 1:
        return f"{names[0]} was down"
    if len(names) == 2:
        return f"{names[0]} and {names[1]} were down"
    return f"{', '.join(names[:-1])}, and {names[-1]} were down"


def _utc_day(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _uptime_from_counts(
    rows: list[tuple[str, int, int, int, int, int, int, int, int]],
) -> dict[str, float | None]:
    by_service = {row[0]: row[1:] for row in rows}
    windows = []
    for key, _name in MONITORS:
        totals = by_service.get(key, (0, 0, 0, 0, 0, 0, 0, 0))
        windows.append(
            (
                _pct(totals[1], totals[0]),
                _pct(totals[3], totals[2]),
                _pct(totals[5], totals[4]),
                _pct(totals[7], totals[6]),
            )
        )
    return {
        "hours_24": _worst([row[0] for row in windows]),
        "days_7": _worst([row[1] for row in windows]),
        "days_30": _worst([row[2] for row in windows]),
        "days_90": _worst([row[3] for row in windows]),
    }


def _bar_map(rows: list[tuple[str, object, bool]]) -> dict[str, dict[str, str]]:
    mapped: dict[str, dict[str, str]] = {}
    for service, day, all_ok in rows:
        tone = "up" if all_ok else "degraded"
        mapped.setdefault(service, {})[str(day)] = tone
    return mapped


def _bars_for(service: str, by_service: dict[str, dict[str, str]], today) -> list[str]:
    days = [(today - timedelta(days=offset)).date().isoformat() for offset in range(29, -1, -1)]
    known = by_service.get(service, {})
    return [known.get(day, "empty") for day in days]


def _hour_key(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _hours_for(
    service: str, rows: list[tuple[str, datetime, float]], start: datetime
) -> list[float | None]:
    known = {
        _hour_key(hour): median for row_service, hour, median in rows if row_service == service
    }
    return [known.get(start + timedelta(hours=index)) for index in range(24)]


def _incidents(rows: list[tuple[object, str]], today) -> list[dict[str, str]]:
    names = {key: name for key, name in MONITORS}
    by_day: dict[str, list[str]] = {}
    for day, service in rows:
        label = names.get(service)
        if label:
            by_day.setdefault(str(day), []).append(label)
    items = []
    for offset in range(7):
        day = (today - timedelta(days=offset)).date().isoformat()
        down = [name for key, name in MONITORS if name in by_day.get(day, [])]
        items.append({"date": day, "summary": _incident_summary(down)})
    return items


async def build_status_history(
    session: AsyncSession, now: datetime, services: dict[str, str]
) -> dict[str, Any]:
    repo = StatusSampleRepository(session)
    today = _utc_day(now)
    hour_end = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    hour_start = hour_end - timedelta(hours=23)
    counts = await repo.uptime_counts(now)
    bars = _bar_map(await repo.availability_days(today - timedelta(days=29)))
    hours = await repo.hourly_medians(hour_start)
    downs = await repo.down_services_by_day(today - timedelta(days=6))
    monitors = [
        {
            "key": key,
            "name": name,
            "state": services.get(key, "ok"),
            "availability_30d": _bars_for(key, bars, today),
            "latency_24h": _hours_for(key, hours, hour_start),
        }
        for key, name in MONITORS
    ]
    return {
        "uptime": _uptime_from_counts(counts),
        "monitors": monitors,
        "incidents": _incidents(downs, today),
    }
