from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.db import SessionDep
from app.security.deps import CurrentAdmin, CurrentUser
from app.services.conversation_queries import EXPORT_MAX, EXPORTABLE_COLUMNS, ConversationQueries
from app.services.conversation_types import CommandError
from app.services.handoff_service import HandoffError, HandoffService
from app.services.rate_limit import RateLimiter, RateLimitExceeded, RateLimitUnavailable

router = APIRouter()


class AssignedAgentOut(BaseModel):
    id: UUID
    display_name: str


class ConversationListItemOut(BaseModel):
    id: UUID
    visitor_display: str
    site_id: UUID
    site_name: str
    state: str
    preview: str
    last_message_at: datetime
    assigned_agent: AssignedAgentOut | None


class InboxSiteOut(BaseModel):
    id: UUID
    name: str
    queued: int


class ConversationListOut(BaseModel):
    items: list[ConversationListItemOut]
    next_cursor: str | None
    counts: dict[str, int]
    sites: list[InboxSiteOut]


class VisitorFactsOut(BaseModel):
    name: str | None
    email: str | None
    phone: str | None
    ip: str | None
    user_agent: str | None
    location: str | None


class PageFactsOut(BaseModel):
    title: str | None
    url: str | None
    referrer: str | None


class CitationOut(BaseModel):
    source_url: str | None
    source_title: str | None
    cited_text: str | None = None


class MessageOut(BaseModel):
    id: int
    role: str
    author_user: AssignedAgentOut | None
    body: str
    source_article_ids: list[UUID] | None
    source_chunk_ids: list[UUID] | None
    source_urls: list[str] | None = None
    display_locator: str | None = None
    source_title: str | None = None
    system_reason: str | None = None
    citations: list[CitationOut] = Field(default_factory=list)
    created_at: datetime


class ConversationDetailOut(BaseModel):
    id: UUID
    site_id: UUID
    site_name: str
    state: str
    inquiry_type: str | None
    intent: str | None
    attention_needed: bool
    escalation_reason: str | None = None
    human_enabled: bool
    bot_enabled: bool
    assigned_agent: AssignedAgentOut | None
    visitor: VisitorFactsOut
    page: PageFactsOut
    messages: list[MessageOut]
    has_older: bool = False
    older_before_id: int | None = None
    blocked: bool
    block_id: UUID | None


class SubmissionVisitorOut(BaseModel):
    name: str | None
    email: str | None
    phone: str | None
    ip: str | None
    user_agent: str | None
    geo_country: str | None
    geo_region: str | None
    location: str | None
    created_at: datetime


class SubmissionItemOut(BaseModel):
    id: UUID
    site_id: UUID
    site_key: str
    site_name: str
    state: str
    inquiry_type: str | None
    intent: str | None
    attention_needed: bool
    opening_message: str | None
    assigned_agent: AssignedAgentOut | None
    visitor: SubmissionVisitorOut
    page: PageFactsOut
    created_at: datetime
    last_message_at: datetime
    closed_at: datetime | None
    blocked: bool
    block_id: UUID | None


class SubmissionListOut(BaseModel):
    items: list[SubmissionItemOut]
    has_more: bool


class SubmissionExportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(min_length=1, max_length=len(EXPORTABLE_COLUMNS))
    site_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None


def _map_command_error(exc: CommandError) -> HTTPException:
    if exc.code == "export_too_large":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Export exceeds {EXPORT_MAX:,} rows. Narrow the site or date filters.",
        )
    if exc.code == "not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if exc.code == "unknown_column":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown column."
        )
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")


@router.get("/api/conversations", response_model=ConversationListOut)
async def list_conversations(
    session: SessionDep,
    _staff: CurrentUser,
    state: Annotated[str | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    site_id: Annotated[UUID | None, Query()] = None,
) -> ConversationListOut:
    service = ConversationQueries(session)
    try:
        items, next_cursor, counts, sites = await service.list_inbox(state, cursor, site_id)
    except CommandError as exc:
        raise _map_command_error(exc) from exc
    return ConversationListOut.model_validate(
        {"items": items, "next_cursor": next_cursor, "counts": counts, "sites": sites}
    )


@router.get("/api/conversations/submissions", response_model=SubmissionListOut)
async def list_submissions(
    session: SessionDep,
    _staff: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int | None, Query(ge=1, le=50)] = None,
) -> SubmissionListOut:
    service = ConversationQueries(session)
    items, has_more = await service.list_submissions(offset, limit)
    return SubmissionListOut.model_validate({"items": items, "has_more": has_more})


@router.get("/api/conversations/submissions/{conversation_id}", response_model=SubmissionItemOut)
async def get_submission(
    conversation_id: UUID, session: SessionDep, _staff: CurrentUser
) -> SubmissionItemOut:
    try:
        return SubmissionItemOut.model_validate(
            await ConversationQueries(session).get_submission(conversation_id)
        )
    except CommandError as exc:
        raise _map_command_error(exc) from exc


@router.post("/api/conversations/submissions/export")
async def export_submissions(
    payload: SubmissionExportIn,
    session: SessionDep,
    _staff: CurrentUser,
) -> Response:
    service = ConversationQueries(session)
    try:
        csv_body = await service.export_submissions(
            payload.columns, payload.site_id, payload.date_from, payload.date_to
        )
    except CommandError as exc:
        raise _map_command_error(exc) from exc
    return Response(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="supportchat-submissions.csv"'},
    )


@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: UUID,
    session: SessionDep,
    _staff: CurrentUser,
    before_id: int | None = None,
) -> ConversationDetailOut:
    service = ConversationQueries(session)
    try:
        detail = await service.get_inbox_detail(conversation_id, before_id=before_id)
    except CommandError as exc:
        raise _map_command_error(exc) from exc
    return ConversationDetailOut.model_validate(detail)


class HandoffOutcomeOut(BaseModel):
    outcome: str
    note: str | None
    resolved_at: datetime
    resolved_by: UUID | None


class HandoffContextOut(BaseModel):
    id: UUID
    conversation_id: UUID
    site_id: UUID
    created_at: datetime
    escalation_reason: str
    original_question: str
    clarification_answer: str | None
    machine_summary: str
    machine_summary_model: str
    candidate_unit_ids: list[UUID]
    rejection_reasons: list[dict]
    provider_stage_timings: dict
    provider_status: str
    promised_response_by: datetime | None
    route: str
    snapshot_id: UUID | None
    outcome: HandoffOutcomeOut | None = None
    candidates: list[dict] = Field(default_factory=list)


class HandoffOutcomeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["resolved", "callback_completed", "no_response", "abandoned", "duplicate"]
    note: str | None = Field(default=None, max_length=280)


def _handoff_http_error(exc: HandoffError) -> HTTPException:
    if exc.code == "not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if exc.code == "already_resolved":
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already resolved")
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")


@router.get("/api/conversations/{conversation_id}/handoff", response_model=HandoffContextOut)
async def get_conversation_handoff(
    conversation_id: UUID,
    session: SessionDep,
    _staff: CurrentUser,
) -> HandoffContextOut:
    service = HandoffService(session)
    detail = await service.get_detail(conversation_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    unit_ids = [UUID(item) for item in detail["candidate_unit_ids"]]
    labels = await service.candidate_labels(unit_ids)
    candidates = []
    rejection_by_id = {
        str(item.get("unit_id")): item.get("reason")
        for item in (detail.get("rejection_reasons") or [])
        if isinstance(item, dict)
    }
    for unit_id in unit_ids:
        meta = labels.get(unit_id, {})
        candidates.append(
            {
                "unit_id": str(unit_id),
                "canonical_question": meta.get("canonical_question"),
                "heading": meta.get("heading"),
                "rejection_reason": rejection_by_id.get(str(unit_id)),
            }
        )
    detail["candidates"] = candidates
    return HandoffContextOut.model_validate(detail)


@router.post("/api/handoffs/{handoff_id}/outcome", response_model=HandoffContextOut)
async def post_handoff_outcome(
    handoff_id: UUID,
    payload: HandoffOutcomeIn,
    session: SessionDep,
    staff: CurrentUser,
) -> HandoffContextOut:
    service = HandoffService(session)
    try:
        await service.close_handoff(handoff_id, payload.outcome, staff.id, payload.note)
        await session.commit()
    except HandoffError as exc:
        await session.rollback()
        raise _handoff_http_error(exc) from exc
    detail = await service.get_detail_by_id(handoff_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return HandoffContextOut.model_validate(detail)


@router.post("/api/handoffs/{handoff_id}/summary/regenerate", response_model=HandoffContextOut)
async def regenerate_handoff_summary(
    handoff_id: UUID,
    session: SessionDep,
    _admin: CurrentAdmin,
) -> HandoffContextOut:
    try:
        await RateLimiter().hit("handoff-summary", 3, 60, str(handoff_id))
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limited"
        ) from exc
    except RateLimitUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limit store unavailable",
        ) from exc
    service = HandoffService(session)
    try:
        await service.regenerate_summary(handoff_id)
        await session.commit()
    except HandoffError as exc:
        await session.rollback()
        raise _handoff_http_error(exc) from exc
    detail = await service.get_detail_by_id(handoff_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return HandoffContextOut.model_validate(detail)
