from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from app.db import SessionDep
from app.models.canned_reply import CannedReply
from app.security.deps import CurrentUser
from app.services.canned_reply_service import CannedReplyError, CannedReplyService

router = APIRouter()


class CannedReplyCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: UUID | None = None
    shortcut: str
    body: str
    enabled: bool = True


class CannedReplyPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: UUID | None = None
    shortcut: str | None = None
    body: str | None = None
    enabled: bool | None = None


class CannedReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    site_id: UUID | None
    shortcut: str
    body: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class CannedReplyLibraryOut(BaseModel):
    items: list[CannedReplyOut]


class EffectiveCannedReplyOut(BaseModel):
    shortcut: str
    body: str
    scope: str


class CannedReplyListOut(BaseModel):
    items: list[EffectiveCannedReplyOut]


def _http_error(exc: CannedReplyError) -> HTTPException:
    if exc.code in {"not_found", "site_not_found"}:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if exc.code == "conflict":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A response with this shortcut already exists in this scope.",
        )
    if exc.code == "empty_update":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provide at least one field to update.",
        )
    if exc.code == "invalid_shortcut":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Shortcut must be 1-40 lowercase letters, numbers, underscores, or hyphens.",
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Message must contain between 1 and 4,000 characters.",
    )


def _out(reply: CannedReply) -> CannedReplyOut:
    return CannedReplyOut.model_validate(reply)


@router.get("/api/canned-replies", response_model=CannedReplyListOut)
async def list_canned_replies(
    session: SessionDep,
    _staff: CurrentUser,
    site_id: Annotated[UUID, Query()],
) -> CannedReplyListOut:
    try:
        rows = await CannedReplyService(session).list_effective(site_id)
    except CannedReplyError as exc:
        raise _http_error(exc) from exc
    return CannedReplyListOut(
        items=[
            EffectiveCannedReplyOut(
                shortcut=row.shortcut,
                body=row.body,
                scope="general" if row.site_id is None else "website",
            )
            for row in rows
        ]
    )


@router.get("/api/canned-replies/library", response_model=CannedReplyLibraryOut)
async def list_canned_reply_library(
    session: SessionDep, _staff: CurrentUser
) -> CannedReplyLibraryOut:
    rows = await CannedReplyService(session).list_library()
    return CannedReplyLibraryOut(items=[_out(row) for row in rows])


@router.post(
    "/api/canned-replies", response_model=CannedReplyOut, status_code=status.HTTP_201_CREATED
)
async def create_canned_reply(
    payload: CannedReplyCreateIn, session: SessionDep, _staff: CurrentUser
) -> CannedReplyOut:
    try:
        reply = await CannedReplyService(session).create(**payload.model_dump())
    except CannedReplyError as exc:
        raise _http_error(exc) from exc
    return _out(reply)


@router.patch("/api/canned-replies/{response_id}", response_model=CannedReplyOut)
async def patch_canned_reply(
    response_id: UUID, payload: CannedReplyPatchIn, session: SessionDep, _staff: CurrentUser
) -> CannedReplyOut:
    fields = set(payload.model_fields_set)
    try:
        reply = await CannedReplyService(session).update(
            response_id, fields=fields, **payload.model_dump()
        )
    except CannedReplyError as exc:
        raise _http_error(exc) from exc
    return _out(reply)


@router.delete("/api/canned-replies/{response_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_canned_reply(response_id: UUID, session: SessionDep, _staff: CurrentUser) -> None:
    try:
        await CannedReplyService(session).delete(response_id)
    except CannedReplyError as exc:
        raise _http_error(exc) from exc
