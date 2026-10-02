"""Staff status board — infrastructure, desk load, knowledge, recent failures."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import SessionDep
from app.security.deps import CurrentUser
from app.services.status_service import build_status_snapshot

router = APIRouter()

ServiceState = Literal["ok", "down", "silent"]
OverallState = Literal["ok", "attention", "degraded"]
KnowledgeTone = Literal["none", "ready", "queued", "running", "failed"]


class StatusServicesOut(BaseModel):
    api: ServiceState
    postgres: ServiceState
    redis: ServiceState
    worker: ServiceState


class StatusLiveOut(BaseModel):
    visitors: int
    specialists: int


class StatusInboxOut(BaseModel):
    waiting: int
    bot: int
    live: int
    closed_today: int


class StatusKnowledgeOut(BaseModel):
    ready: int
    running: int
    failed: int
    queued: int


class StatusErrorOut(BaseModel):
    id: UUID
    created_at: datetime
    event: str
    message: str
    source: str


class StatusSiteOut(BaseModel):
    id: UUID
    key: str
    name: str
    enabled: bool
    bot_enabled: bool
    human_enabled: bool
    widget_installed: bool | None
    waiting: int
    knowledge: KnowledgeTone


class StatusUptimeOut(BaseModel):
    hours_24: float | None
    days_7: float | None
    days_30: float | None
    days_90: float | None


class StatusMonitorOut(BaseModel):
    key: str
    name: str
    state: ServiceState
    availability_30d: list[Literal["empty", "up", "degraded"]]
    latency_24h: list[float | None]


class StatusIncidentOut(BaseModel):
    date: str
    summary: str


class StatusOut(BaseModel):
    checked_at: datetime
    overall: OverallState
    headline: str
    services: StatusServicesOut
    live: StatusLiveOut
    inbox: StatusInboxOut
    knowledge: StatusKnowledgeOut
    gaps_open: int
    errors_24h: int
    recent_errors: list[StatusErrorOut]
    sites: list[StatusSiteOut]
    uptime: StatusUptimeOut
    monitors: list[StatusMonitorOut]
    incidents: list[StatusIncidentOut]


@router.get("/api/status", response_model=StatusOut)
async def staff_status(session: SessionDep, _staff: CurrentUser) -> StatusOut:
    return StatusOut.model_validate(await build_status_snapshot(session))
