from datetime import datetime
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from app.db import SessionDep
from app.repositories.canned_import_repo import CannedImportRepository
from app.security.deps import CurrentUser

router = APIRouter(prefix="/api/canned-replies/imports")


class ImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    uploaded_at: datetime
    uploaded_by_name: str | None
    sha256: str
    created: int
    updated: int
    skipped: int


class ImportRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    row_number: int
    reply_id: UUID | None
    action: str
    snapshot: dict[str, Any]


class ImportListOut(BaseModel):
    items: list[ImportOut]
    has_more: bool


class ImportDetailOut(BaseModel):
    batch: ImportOut
    rows: list[ImportRowOut]
    has_more: bool


@router.get("", response_model=ImportListOut)
async def list_imports(
    session: SessionDep,
    _staff: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ImportListOut:
    batches, has_more = await CannedImportRepository(session).list_batches(offset, limit)
    return ImportListOut(
        items=[ImportOut.model_validate(batch) for batch in batches], has_more=has_more
    )


@router.get("/{import_id}", response_model=ImportDetailOut)
async def get_import(
    import_id: int,
    session: SessionDep,
    _staff: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ImportDetailOut:
    repo = CannedImportRepository(session)
    batch = await repo.get_batch(import_id)
    if batch is None:
        raise HTTPException(404, "Upload not found")
    rows, has_more = await repo.rows(import_id, offset, limit)
    return ImportDetailOut(
        batch=ImportOut.model_validate(batch),
        rows=[ImportRowOut.model_validate(row) for row in rows],
        has_more=has_more,
    )


@router.get("/{import_id}/file")
async def download_import(import_id: int, session: SessionDep, _staff: CurrentUser) -> Response:
    batch = await CannedImportRepository(session).get_batch(import_id)
    if batch is None:
        raise HTTPException(404, "Upload not found")
    return Response(
        content=batch.raw_csv,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(batch.filename, safe='')}"
        },
    )
