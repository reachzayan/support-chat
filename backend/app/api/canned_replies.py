from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from app.db import SessionDep
from app.models.canned_reply import CannedReply
from app.security.deps import CurrentAdmin, CurrentUser
from app.services.canned_import import BODY_MAX, ImportPlanRow, bot_block_reason
from app.services.canned_reply_service import CannedReplyError, CannedReplyService

router = APIRouter()


class CannedReplyCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: UUID | None = None
    shortcut: str
    body: str
    enabled: bool = True
    aliases: list[str] = Field(default_factory=list)
    bot_eligible: bool = True
    follows_id: UUID | None = None
    hands_off: bool = False


class CannedReplyPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: UUID | None = None
    shortcut: str | None = None
    body: str | None = None
    enabled: bool | None = None
    aliases: list[str] | None = None
    bot_eligible: bool | None = None
    follows_id: UUID | None = None
    hands_off: bool | None = None


class CannedReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    site_id: UUID | None
    shortcut: str
    body: str
    enabled: bool
    aliases: list[str]
    external_id: int | None
    suggestion_event: str | None
    bot_eligible: bool
    follows_id: UUID | None
    hands_off: bool
    # Set when the row is switched on but the bot still cannot use its wording.
    bot_block_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class CannedReplyLibraryOut(BaseModel):
    items: list[CannedReplyOut]


class EffectiveCannedReplyOut(BaseModel):
    shortcut: str
    body: str
    scope: str
    aliases: list[str]


class CannedReplyListOut(BaseModel):
    items: list[EffectiveCannedReplyOut]


class CannedImportRowOut(BaseModel):
    action: str
    reason: str | None
    livechat_id: int | None
    group: int | None
    group_name: str | None
    livechat_website: str | None
    site_id: UUID | None
    shortcut: str
    aliases: list[str]
    bot_eligible: bool
    disable_reason: str | None
    suggestion_event: str | None
    excerpt: str


class ImportDecisionsIn(BaseModel):
    discard_ids: list[int] = Field(default_factory=list)
    remap_groups: dict[str, UUID | None] = Field(default_factory=dict)


class CannedImportPreviewOut(BaseModel):
    created: int
    updated: int
    skipped: int
    rows: list[CannedImportRowOut]


class CannedImportCommitOut(BaseModel):
    created: int
    updated: int
    skipped: int


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
    if exc.code == "forbidden":
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if exc.code == "invalid_shortcut":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Shortcut must be 1-40 lowercase letters, numbers, underscores, or hyphens.",
        )
    if exc.code == "invalid_follows":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Choose a different response from General or this website to follow.",
        )
    if exc.code == "unmapped_group":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Choose a website for each LiveChat group, or discard those responses.",
        )
    if exc.code == "invalid_csv":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Upload a LiveChat canned-response CSV with id, text, tags, and group columns.",
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Message must contain between 1 and {BODY_MAX:,} characters.",
    )


def _out(reply: CannedReply) -> CannedReplyOut:
    out = CannedReplyOut.model_validate(reply)
    out.bot_block_reason = bot_block_reason(reply.body)
    return out


def _preview_row(row: ImportPlanRow) -> CannedImportRowOut:
    return CannedImportRowOut(
        action=row.action,
        reason=row.reason,
        livechat_id=row.livechat_id,
        group=row.group,
        group_name=row.group_name,
        livechat_website=row.livechat_website,
        site_id=row.site_id,
        shortcut=row.shortcut,
        aliases=list(row.aliases),
        bot_eligible=row.bot_eligible,
        disable_reason=row.disable_reason,
        suggestion_event=row.suggestion_event,
        excerpt=row.excerpt,
    )


async def _read_csv(file: UploadFile) -> bytes:
    raw = await file.read()
    if not raw:
        raise CannedReplyError("invalid_csv")
    return raw


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
                aliases=list(row.aliases or []),
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


@router.post("/api/canned-replies/import/preview", response_model=CannedImportPreviewOut)
async def preview_canned_import(
    session: SessionDep,
    _admin: CurrentAdmin,
    file: Annotated[UploadFile, File()],
) -> CannedImportPreviewOut:
    try:
        rows = await CannedReplyService(session).preview_import(await _read_csv(file))
    except CannedReplyError as exc:
        raise _http_error(exc) from exc
    return CannedImportPreviewOut(
        created=sum(row.action == "create" for row in rows),
        updated=sum(row.action == "update" for row in rows),
        skipped=sum(row.action == "skip" for row in rows),
        rows=[_preview_row(row) for row in rows],
    )


def _parse_decisions(raw: str | None) -> tuple[set[int], dict[int, UUID | None]]:
    if not raw:
        return set(), {}
    try:
        parsed = ImportDecisionsIn.model_validate_json(raw)
    except ValueError as exc:
        raise CannedReplyError("invalid_csv") from exc
    remaps: dict[int, UUID | None] = {}
    for key, site_id in parsed.remap_groups.items():
        if not key.isdigit():
            raise CannedReplyError("invalid_csv")
        remaps[int(key)] = site_id
    return set(parsed.discard_ids), remaps


@router.post("/api/canned-replies/import", response_model=CannedImportCommitOut)
async def commit_canned_import(
    session: SessionDep,
    _admin: CurrentAdmin,
    file: Annotated[UploadFile, File()],
    decisions: Annotated[str | None, Form()] = None,
) -> CannedImportCommitOut:
    try:
        discard_ids, remap_groups = _parse_decisions(decisions)
        counts = await CannedReplyService(session).commit_import(
            await _read_csv(file),
            discard_ids=discard_ids,
            remap_groups=remap_groups,
        )
    except CannedReplyError as exc:
        raise _http_error(exc) from exc
    return CannedImportCommitOut(**counts)


@router.post(
    "/api/canned-replies", response_model=CannedReplyOut, status_code=status.HTTP_201_CREATED
)
async def create_canned_reply(
    payload: CannedReplyCreateIn, session: SessionDep, staff: CurrentUser
) -> CannedReplyOut:
    try:
        reply = await CannedReplyService(session).create(
            **payload.model_dump(), is_admin=staff.is_admin
        )
    except CannedReplyError as exc:
        raise _http_error(exc) from exc
    return _out(reply)


@router.patch("/api/canned-replies/{response_id}", response_model=CannedReplyOut)
async def patch_canned_reply(
    response_id: UUID, payload: CannedReplyPatchIn, session: SessionDep, staff: CurrentUser
) -> CannedReplyOut:
    fields = set(payload.model_fields_set)
    try:
        reply = await CannedReplyService(session).update(
            response_id, fields=fields, is_admin=staff.is_admin, **payload.model_dump()
        )
    except CannedReplyError as exc:
        raise _http_error(exc) from exc
    return _out(reply)


@router.delete("/api/canned-replies/{response_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_canned_reply(response_id: UUID, session: SessionDep, staff: CurrentUser) -> None:
    try:
        await CannedReplyService(session).delete(response_id, is_admin=staff.is_admin)
    except CannedReplyError as exc:
        raise _http_error(exc) from exc
