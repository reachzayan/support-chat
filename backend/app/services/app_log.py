"""Persist elaborative application logs with PII/transcript redaction."""

from __future__ import annotations

import json
import re
from datetime import UTC
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import _SENSITIVE
from app.models.app_log import AppLog
from app.repositories.app_log_repo import DEFAULT_RETENTION_DAYS, AppLogRepository

__all__ = [
    "DEFAULT_RETENTION_DAYS",
    "format_log_dump_line",
    "record_app_log",
    "sanitize_log_detail",
    "sanitize_log_message",
]

_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+"
)
_URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)


def _strip_url_secrets(match: re.Match[str]) -> str:
    raw = match.group(0)
    parsed = urlsplit(raw)
    if not parsed.query and not parsed.fragment:
        return raw
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def sanitize_log_message(value: str) -> str:
    """Remove credentials and common direct identifiers from untrusted log text."""
    cleaned = _URL_RE.sub(_strip_url_secrets, value)
    cleaned = _BEARER_RE.sub("Bearer [redacted]", cleaned)
    cleaned = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[redacted]", cleaned)
    cleaned = _EMAIL_RE.sub("[redacted]", cleaned)
    return _SSN_RE.sub("[redacted]", cleaned)


def _sanitize_log_value(value: Any) -> Any:
    if isinstance(value, dict):
        return sanitize_log_detail(value)
    if isinstance(value, list):
        return [_sanitize_log_value(item) for item in value]
    if isinstance(value, str):
        return sanitize_log_message(value)
    return value


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
            cleaned[key] = [_sanitize_log_value(item) for item in value]
            continue
        cleaned[key] = _sanitize_log_value(value)
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
        message=sanitize_log_message(message)[:8000],
        detail=sanitize_log_detail(detail),
    )
    return await AppLogRepository(session).add(row)


def _safe_log_field(text: str) -> str:
    return text.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


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
    message = _safe_log_field(row.message)
    return (
        f"{iso} {row.level.upper()} source={row.source} logger={row.logger_name} "
        f"event={row.event} message={message}{detail_text}"
    )
