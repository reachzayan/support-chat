from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db import SessionDep
from app.security.deps import CurrentUser
from app.services.conversation_service import ConversationService

router = APIRouter()


class CannedReplyOut(BaseModel):
    shortcut: str
    body: str


class CannedReplyListOut(BaseModel):
    items: list[CannedReplyOut]


@router.get("/api/canned-replies", response_model=CannedReplyListOut)
async def list_canned_replies(
    session: SessionDep,
    _staff: CurrentUser,
    site_id: Annotated[UUID, Query()],
) -> CannedReplyListOut:
    items = await ConversationService(session).list_canned_replies(site_id)
    return CannedReplyListOut.model_validate({"items": items})
