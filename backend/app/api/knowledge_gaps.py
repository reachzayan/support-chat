from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.db import SessionDep
from app.security.deps import CurrentUser
from app.services.canned_reply_service import CannedReplyError
from app.services.kb_embedder import Embedder, default_embedder
from app.services.knowledge_gap_answers import answer_with_canned_reply, answer_with_knowledge_text
from app.services.knowledge_gap_service import (
    NOTE_MAX,
    KnowledgeGapError,
    KnowledgeGapService,
    QueueItem,
)
from app.services.knowledge_gap_similar import closest_entries
from app.services.site_admin import AdminError

router = APIRouter()


def get_embedder() -> Embedder:
    return default_embedder()


EmbedderDep = Annotated[Embedder, Depends(get_embedder)]


class GapOut(BaseModel):
    id: UUID
    site_id: UUID
    question: str
    conversations: int
    last_seen_at: datetime
    examples: list[str]
    spiking: bool
    note: str | None
    status: str
    resolved_at: datetime | None


class GapListOut(BaseModel):
    items: list[GapOut]
    min_conversations: int
    window_days: int
    spike_conversations: int
    spike_hours: int


class RepliesOut(BaseModel):
    items: list[str]


class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=NOTE_MAX)


class ClosestCannedOut(BaseModel):
    id: UUID
    site_id: UUID | None
    shortcut: str
    excerpt: str
    enabled: bool
    bot_eligible: bool
    similarity: float


class ClosestKnowledgeOut(BaseModel):
    title: str
    heading: str
    url: str
    similarity: float


class SimilarOut(BaseModel):
    canned: ClosestCannedOut | None
    knowledge: ClosestKnowledgeOut | None


class BadgeGapOut(BaseModel):
    id: UUID
    question: str
    conversations: int
    spiking: bool


class BadgeOut(BaseModel):
    gap: BadgeGapOut | None


class CannedAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["canned"]
    shortcut: str
    body: str


class KnowledgeAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["knowledge"]
    title: str
    body: str


AnswerIn = Annotated[CannedAnswerIn | KnowledgeAnswerIn, Field(discriminator="kind")]

EXCERPT_CHARS = 160
_NOT_FOUND = {"not_found", "site_not_found"}
_CONFLICT = {
    "not_open": "This question was already handled.",
    "already_open": "This question is already open.",
    "conflict": "A response with this shortcut already exists in this scope.",
}


def _http_error(exc: KnowledgeGapError | CannedReplyError | AdminError) -> HTTPException:
    if exc.code in _NOT_FOUND:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if exc.code in _CONFLICT:
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_CONFLICT[exc.code])
    if exc.code == "forbidden":
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Check the shortcut or title and the answer, then try again.",
    )


def _gap_out(item: QueueItem) -> GapOut:
    return GapOut(
        id=item.id,
        site_id=item.site_id,
        question=item.question,
        conversations=item.conversations,
        last_seen_at=item.last_seen_at,
        examples=item.examples,
        spiking=item.spiking,
        note=item.note,
        status=item.status,
        resolved_at=item.resolved_at,
    )


@router.get("/api/knowledge-gaps", response_model=GapListOut)
async def list_knowledge_gaps(
    session: SessionDep,
    _staff: CurrentUser,
    site_id: Annotated[UUID | None, Query()] = None,
    view: Annotated[Literal["open", "answered", "dismissed"], Query(alias="status")] = "open",
) -> GapListOut:
    queue = await KnowledgeGapService(session).queue(site_id, view)
    return GapListOut(
        items=[_gap_out(item) for item in queue.items],
        min_conversations=queue.min_conversations,
        window_days=queue.window_days,
        spike_conversations=queue.spike_conversations,
        spike_hours=queue.spike_hours,
    )


@router.get("/api/knowledge-gaps/{gap_id}/replies", response_model=RepliesOut)
async def knowledge_gap_replies(
    gap_id: UUID, session: SessionDep, _staff: CurrentUser
) -> RepliesOut:
    try:
        return RepliesOut(items=await KnowledgeGapService(session).specialist_replies(gap_id))
    except KnowledgeGapError as exc:
        raise _http_error(exc) from exc


@router.get("/api/knowledge-gaps/{gap_id}/similar", response_model=SimilarOut)
async def knowledge_gap_similar(
    gap_id: UUID, session: SessionDep, _staff: CurrentUser, embedder: EmbedderDep
) -> SimilarOut:
    gap = await KnowledgeGapService(session).get_gap(gap_id)
    if gap is None:
        raise _http_error(KnowledgeGapError("not_found"))
    closest = await closest_entries(session, embedder, gap)
    canned = closest.canned
    knowledge = closest.knowledge
    return SimilarOut(
        canned=None
        if canned is None
        else ClosestCannedOut(
            id=canned.reply.id,
            site_id=canned.reply.site_id,
            shortcut=canned.reply.shortcut,
            excerpt=canned.reply.body[:EXCERPT_CHARS],
            enabled=canned.reply.enabled,
            bot_eligible=canned.reply.bot_eligible,
            similarity=round(canned.similarity, 2),
        ),
        knowledge=None
        if knowledge is None
        else ClosestKnowledgeOut(
            title=knowledge.title,
            heading=knowledge.heading,
            url=knowledge.url,
            similarity=round(knowledge.similarity, 2),
        ),
    )


@router.get("/api/conversations/{conversation_id}/knowledge-gap", response_model=BadgeOut)
async def conversation_knowledge_gap(
    conversation_id: UUID, session: SessionDep, _staff: CurrentUser
) -> BadgeOut:
    item = await KnowledgeGapService(session).for_conversation(conversation_id)
    if item is None:
        return BadgeOut(gap=None)
    return BadgeOut(
        gap=BadgeGapOut(
            id=item.id,
            question=item.question,
            conversations=item.conversations,
            spiking=item.spiking,
        )
    )


@router.patch("/api/knowledge-gaps/{gap_id}", status_code=status.HTTP_204_NO_CONTENT)
async def set_knowledge_gap_note(
    gap_id: UUID, payload: NoteIn, session: SessionDep, _staff: CurrentUser
) -> None:
    try:
        await KnowledgeGapService(session).set_note(gap_id, payload.note)
    except KnowledgeGapError as exc:
        raise _http_error(exc) from exc


@router.post("/api/knowledge-gaps/{gap_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_knowledge_gap(gap_id: UUID, session: SessionDep, staff: CurrentUser) -> None:
    try:
        await KnowledgeGapService(session).dismiss(gap_id, staff)
    except KnowledgeGapError as exc:
        raise _http_error(exc) from exc


@router.post("/api/knowledge-gaps/{gap_id}/reopen", status_code=status.HTTP_204_NO_CONTENT)
async def reopen_knowledge_gap(gap_id: UUID, session: SessionDep, _staff: CurrentUser) -> None:
    try:
        await KnowledgeGapService(session).reopen(gap_id)
    except KnowledgeGapError as exc:
        raise _http_error(exc) from exc


@router.post("/api/knowledge-gaps/{gap_id}/answer", status_code=status.HTTP_204_NO_CONTENT)
async def answer_knowledge_gap(
    gap_id: UUID, payload: AnswerIn, session: SessionDep, staff: CurrentUser
) -> None:
    try:
        if payload.kind == "canned":
            await answer_with_canned_reply(
                session, gap_id, staff, shortcut=payload.shortcut, body=payload.body
            )
        else:
            await answer_with_knowledge_text(
                session, gap_id, staff, title=payload.title, body=payload.body
            )
    except (KnowledgeGapError, CannedReplyError, AdminError) as exc:
        raise _http_error(exc) from exc
