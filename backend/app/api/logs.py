"""Admin application logs — list, 7-day dump, and frontend client reports."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

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
    model_config = ConfigDict(extra="forbid")

    event: Literal["ui_window_error", "ui_unhandled_rejection"]
    error_class: Literal[
        "Error",
        "TypeError",
        "ReferenceError",
        "SyntaxError",
        "RangeError",
        "URIError",
        "EvalError",
        "AggregateError",
        "DOMException",
        "AbortError",
        "NetworkError",
        "UnhandledRejection",
    ] = "Error"
    line: int | None = Field(default=None, ge=0, le=1_000_000)
    column: int | None = Field(default=None, ge=0, le=1_000_000)


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


@router.get("/api/logs/{log_id}", response_model=AppLogOut)
async def get_log(log_id: UUID, session: SessionDep, _admin: CurrentAdmin) -> AppLogOut:
    row = await AppLogRepository(session).get(log_id)
    if row is None or row.created_at < datetime.now(UTC) - timedelta(days=DEFAULT_RETENTION_DAYS):
        raise HTTPException(status_code=404, detail="Not found")
    return _to_out(row)


@router.post("/api/logs/client", response_model=AppLogOut, status_code=201)
async def client_log(
    payload: ClientLogIn,
    session: SessionDep,
    staff: CurrentUser,
) -> AppLogOut:
    detail: dict[str, Any] = {"error_class": payload.error_class}
    if payload.line is not None:
        detail["line"] = payload.line
    if payload.column is not None:
        detail["column"] = payload.column
    detail["reported_by_user_id"] = str(staff.id)
    detail["reported_by_is_admin"] = staff.is_admin
    row = await record_app_log(
        session,
        level="error",
        source="frontend",
        logger_name="frontend",
        event=payload.event,
        message=(
            "Unhandled window error"
            if payload.event == "ui_window_error"
            else "Unhandled promise rejection"
        ),
        detail=detail,
    )
    await session.commit()
    return _to_out(row)
