"""Temporary local-only endpoints for exercising and tracing the chatbot."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db import SessionDep
from app.repositories.site_repo import SiteRepository
from app.security.deps import CurrentAdmin
from app.services.canned_bot import inspect_canned_search
from app.services.internal_dev_chat import (
    InternalChatError,
    InternalChatHarness,
    InternalChatRequest,
)
from app.services.kb_embedder import default_embedder
from app.settings import get_settings

router = APIRouter(prefix="/api/internal/dev")


class InternalTurnIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    site_key: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    client_message_id: UUID = Field(default_factory=uuid4)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value


class CitationOut(BaseModel):
    id: UUID
    chunk_id: UUID | None
    snapshot_id: UUID | None
    source_url: str
    source_title: str
    cited_text: str
    response_start: int
    response_end: int
    source_start: int
    source_end: int


class InternalMessageOut(BaseModel):
    id: int
    role: str
    body: str
    client_message_id: UUID | None
    system_reason: str | None
    outcome: str | None
    reason: str | None
    source_article_ids: list[UUID] | None
    source_chunk_ids: list[UUID] | None
    snapshot_id: UUID | None
    source_urls: list[str] | None
    source_title: str | None
    display_locator: str | None
    created_at: datetime
    citations: list[CitationOut]


class InternalTurnOut(BaseModel):
    conversation_id: UUID
    client_message_id: UUID
    duplicate: bool
    state_before: str
    state: str
    fallback_count: int
    intent: str | None
    elapsed_ms: int
    messages: list[InternalMessageOut]
    reply: InternalMessageOut | None


class InternalTraceOut(InternalTurnOut):
    trace: dict[str, Any]


async def _run(payload: InternalTurnIn, session: SessionDep, diagnostics: bool) -> dict[str, Any]:
    request = InternalChatRequest(
        site_key=payload.site_key,
        message=payload.message,
        conversation_id=payload.conversation_id,
        client_message_id=payload.client_message_id,
    )
    try:
        return await InternalChatHarness(session).turn(request, diagnostics=diagnostics)
    except InternalChatError as exc:
        headers = None
        if exc.status_code == 429:
            settings = get_settings()
            headers = {
                "Retry-After": str(
                    max(
                        settings.rate_visitor_submit_window,
                        settings.rate_visitor_submit_ip_window,
                    )
                )
            }
        raise HTTPException(exc.status_code, exc.code, headers=headers) from None


@router.post("/chat", response_model=InternalTurnOut, include_in_schema=False)
async def chat_turn(
    payload: InternalTurnIn,
    response: Response,
    session: SessionDep,
    _admin: CurrentAdmin,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await _run(payload, session, False)


@router.post("/trace", response_model=InternalTraceOut, include_in_schema=False)
async def trace_turn(
    payload: InternalTurnIn,
    response: Response,
    session: SessionDep,
    _admin: CurrentAdmin,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await _run(payload, session, True)


class CannedSearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    site_key: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value


class CannedHitOut(BaseModel):
    shortcut: str
    lexical: bool
    rrf: float
    cosine: float | None


class CannedSearchOut(BaseModel):
    winner: str | None
    best_kb_cosine: float | None
    hits: list[CannedHitOut]


@router.post("/canned-search", response_model=CannedSearchOut, include_in_schema=False)
async def canned_search_turn(
    payload: CannedSearchIn,
    response: Response,
    session: SessionDep,
    _admin: CurrentAdmin,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    site = await SiteRepository(session).get_by_key(payload.site_key)
    if site is None or not site.enabled:
        raise HTTPException(404, "not_found")
    return await inspect_canned_search(session, default_embedder(), site.id, payload.message)
