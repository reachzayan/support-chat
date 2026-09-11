"""Admin application logs — list, 7-day dump, and frontend client reports."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.db import SessionDep
from app.repositories.app_log_repo import DEFAULT_RETENTION_DAYS, AppLogRepository
from app.security.deps import CurrentAdmin, CurrentUser
from app.services.app_log import format_log_dump_line, record_app_log

router = APIRouter()


class AppLogOut(BaseModel):
    id: UUID
    created_at: datetime
    level: str
    source: str
    logger_name: str
    event: str
    message: str
    detail: dict[str, Any] | None = None


class AppLogListOut(BaseModel):
    items: list[AppLogOut]


class ClientLogIn(BaseModel):
    level: str = Field(default="error", max_length=16)
    event: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    detail: dict[str, Any] | None = None
    logger_name: str = Field(default="frontend", max_length=128)


def _to_out(row) -> AppLogOut:
    return AppLogOut(
        id=row.id,
        created_at=row.created_at,
        level=row.level,
        source=row.source,
        logger_name=row.logger_name,
        event=row.event,
        message=row.message,
        detail=row.detail,
    )


@router.get("/api/logs", response_model=AppLogListOut)
async def list_logs(
    session: SessionDep,
    _admin: CurrentAdmin,
    level: Annotated[str | None, Query()] = None,
    source: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> AppLogListOut:
    since = datetime.now(UTC) - timedelta(days=DEFAULT_RETENTION_DAYS)
    rows = await AppLogRepository(session).list_recent(
        since=since, level=level, source=source, limit=limit
    )
    return AppLogListOut(items=[_to_out(row) for row in rows])


@router.get("/api/logs/dump")
async def dump_logs(session: SessionDep, _admin: CurrentAdmin) -> PlainTextResponse:
    since = datetime.now(UTC) - timedelta(days=DEFAULT_RETENTION_DAYS)
    rows = await AppLogRepository(session).list_recent(since=since, limit=2000)
    # Dump oldest → newest for chronological reading.
    lines = [format_log_dump_line(row) for row in reversed(rows)]
    body = "\n".join(lines) + ("\n" if lines else "")
    filename = f"supportchat-logs-{datetime.now(UTC).date().isoformat()}.txt"
    return PlainTextResponse(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/logs/client", response_model=AppLogOut, status_code=201)
async def client_log(
    payload: ClientLogIn,
    request: Request,
    session: SessionDep,
    staff: CurrentUser,
) -> AppLogOut:
    detail = dict(payload.detail or {})
    detail.setdefault("path", request.headers.get("referer"))
    detail["reported_by_user_id"] = str(staff.id)
    detail["reported_by_is_admin"] = staff.is_admin
    row = await record_app_log(
        session,
        level=payload.level,
        source="frontend",
        logger_name=payload.logger_name or "frontend",
        event=payload.event,
        message=payload.message,
        detail=detail,
    )
    await session.commit()
    return _to_out(row)
