"""Persist elaborative application logs with PII/transcript redaction."""

from __future__ import annotations

import json
from datetime import UTC
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import _SENSITIVE
from app.models.app_log import AppLog
from app.repositories.app_log_repo import DEFAULT_RETENTION_DAYS, AppLogRepository

__all__ = [
    "DEFAULT_RETENTION_DAYS",
    "format_log_dump_line",
    "record_app_log",
    "sanitize_log_detail",
]


def sanitize_log_detail(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    if detail is None:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in detail.items():
        lowered = str(key).lower()
        if lowered in _SENSITIVE or "token" in lowered or "password" in lowered:
            continue
        if isinstance(value, dict):
            nested = sanitize_log_detail(value)
            if nested:
                cleaned[key] = nested
            continue
        if isinstance(value, list):
            cleaned[key] = [
                sanitize_log_detail(item) if isinstance(item, dict) else item
                for item in value
                if not (isinstance(item, dict) and sanitize_log_detail(item) is None)
            ]
            continue
        if isinstance(value, str) and ("?" in value or "#" in value) and "://" in value:
            cleaned[key] = value.split("#", 1)[0].split("?", 1)[0]
            continue
        cleaned[key] = value
    return cleaned


async def record_app_log(
    session: AsyncSession,
    *,
    level: str,
    source: str,
    event: str,
    message: str,
    logger_name: str = "",
    detail: dict[str, Any] | None = None,
) -> AppLog:
    row = AppLog(
        level=level.lower()[:16],
        source=source[:32],
        logger_name=(logger_name or "")[:128],
        event=event[:128],
        message=message[:8000],
        detail=sanitize_log_detail(detail),
    )
    return await AppLogRepository(session).add(row)


def format_log_dump_line(row: AppLog) -> str:
    stamp = row.created_at
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    else:
        stamp = stamp.astimezone(UTC)
    iso = stamp.isoformat().replace("+00:00", "Z")
    detail_text = ""
    if row.detail:
        detail_text = " " + json.dumps(row.detail, default=str, separators=(",", ":"))
    return (
        f"{iso} {row.level.upper()} source={row.source} logger={row.logger_name} "
        f"event={row.event} message={row.message}{detail_text}"
    )
