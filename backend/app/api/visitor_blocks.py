from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.chat.connection_manager import connection_manager
from app.db import SessionDep
from app.models.visitor_block import VisitorBlock
from app.security.deps import CurrentUser
from app.services.visitor_block_service import VisitorBlockError, VisitorBlockService

router = APIRouter()


class VisitorBlockCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: UUID
    ip: str | None = None
    email: str | None = None
    phone: str | None = None


class VisitorBlockOut(BaseModel):
    id: UUID
    site_id: UUID
    site_name: str
    ip: str | None
    email: str | None
    phone: str | None
    created_by_name: str
    created_at: datetime


class VisitorBlockListOut(BaseModel):
    items: list[VisitorBlockOut]


def _http_error(exc: VisitorBlockError) -> HTTPException:
    if exc.code == "not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if exc.code == "empty":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Select at least one identifier.",
        )
    if exc.code == "invalid_ip":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="IP address is not valid.",
        )
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")


def _out(block: VisitorBlock, site_name: str, created_by_name: str) -> VisitorBlockOut:
    return VisitorBlockOut(
        id=block.id,
        site_id=block.site_id,
        site_name=site_name,
        ip=str(block.ip) if block.ip is not None else None,
        email=block.email,
        phone=block.phone,
        created_by_name=created_by_name,
        created_at=block.created_at,
    )


@router.get("/api/visitor-blocks", response_model=VisitorBlockListOut)
async def list_visitor_blocks(session: SessionDep, _staff: CurrentUser) -> VisitorBlockListOut:
    rows = await VisitorBlockService(session).list_blocks()
    return VisitorBlockListOut(
        items=[
            _out(block, site_name, created_by_name) for block, site_name, created_by_name in rows
        ]
    )


@router.post(
    "/api/visitor-blocks", response_model=VisitorBlockOut, status_code=status.HTTP_201_CREATED
)
async def create_visitor_block(
    payload: VisitorBlockCreateIn, session: SessionDep, staff: CurrentUser
) -> VisitorBlockOut:
    service = VisitorBlockService(session)
    try:
        created = await service.create(
            payload.site_id,
            staff.id,
            staff.display_name,
            ip=payload.ip,
            email=payload.email,
            phone=payload.phone,
        )
    except VisitorBlockError as exc:
        await session.rollback()
        raise _http_error(exc) from exc
    for conversation, site_key in created.closed:
        await connection_manager.after_commit(conversation, site_key, None)
    return _out(created.block, created.site_name, created.created_by_name)


@router.delete("/api/visitor-blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visitor_block(block_id: UUID, session: SessionDep, _staff: CurrentUser) -> None:
    try:
        await VisitorBlockService(session).delete(block_id)
    except VisitorBlockError as exc:
        await session.rollback()
        raise _http_error(exc) from exc
