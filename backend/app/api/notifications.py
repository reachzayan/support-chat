from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db import SessionDep
from app.repositories.notification_repo import NotificationRepository
from app.security.deps import CurrentUser

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
Scenario = Literal["live", "bot", "needs_attention", "visitor_message", "closed"]


class NotificationOut(BaseModel):
    id: int
    site_id: UUID
    site_name: str
    conversation_id: UUID
    scenario: Scenario
    created_at: datetime
    read_at: datetime | None


class UnreadConversationContext(BaseModel):
    site_id: UUID
    state: Literal["prechat", "bot", "queued", "human", "closed"]


class FeedOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int
    unread_conversations: dict[UUID, int]
    unread_conversation_context: dict[UUID, UnreadConversationContext]
    next_cursor: int | None
    latest_id: int | None


class PushPreferences(BaseModel):
    enabled: bool
    scenarios: list[Scenario]


class SitePreferences(BaseModel):
    site_id: UUID
    site_name: str
    scenarios: dict[Scenario, bool]
    push: PushPreferences


class PreferencesOut(BaseModel):
    sites: list[SitePreferences]


class PreferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    site_id: UUID
    scenario: Scenario
    in_app: bool


class PushPreferenceIn(PushPreferences):
    model_config = ConfigDict(extra="forbid")
    site_id: UUID
    scenarios: list[Scenario] = Field(max_length=5)

    @field_validator("scenarios")
    @classmethod
    def unique_scenarios(cls, value: list[Scenario]) -> list[Scenario]:
        if len(set(value)) != len(value):
            raise ValueError("Choose each notification type only once")
        return value


class ReadAllIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    through_id: int = Field(gt=0)


@router.get("", response_model=FeedOut)
async def feed(
    session: SessionDep,
    staff: CurrentUser,
    cursor: Annotated[int | None, Query(gt=0)] = None,
    unread: bool = False,
) -> FeedOut:
    return FeedOut.model_validate(
        await NotificationRepository(session).list_for_user(staff.id, cursor, unread)
    )


@router.get("/preferences", response_model=PreferencesOut)
async def preferences(session: SessionDep, staff: CurrentUser) -> PreferencesOut:
    return PreferencesOut.model_validate(
        {"sites": await NotificationRepository(session).preferences(staff.id)}
    )


@router.put("/preferences", response_model=PreferenceIn)
async def save_preference(
    payload: PreferenceIn, session: SessionDep, staff: CurrentUser
) -> PreferenceIn:
    found = await NotificationRepository(session).save_preference(
        staff.id,
        payload.site_id,
        payload.scenario,
        payload.in_app,
    )
    if not found:
        raise HTTPException(404, "Site not found")
    await session.commit()
    return payload


@router.post("/read-all", status_code=204)
async def read_all(payload: ReadAllIn, session: SessionDep, staff: CurrentUser) -> None:
    await NotificationRepository(session).mark_all_read(staff.id, payload.through_id)
    await session.commit()


@router.put("/preferences/push", response_model=PushPreferenceIn)
async def save_push_preference(
    payload: PushPreferenceIn, session: SessionDep, staff: CurrentUser
) -> PushPreferenceIn:
    found = await NotificationRepository(session).save_push_preference(
        staff.id, payload.site_id, payload.enabled, payload.scenarios
    )
    if not found:
        raise HTTPException(404, "Site not found")
    await session.commit()
    return payload


@router.post("/conversations/{conversation_id}/read", status_code=204)
async def read_conversation(
    conversation_id: UUID, payload: ReadAllIn, session: SessionDep, staff: CurrentUser
) -> None:
    await NotificationRepository(session).mark_conversation_read(
        staff.id, conversation_id, payload.through_id
    )
    await session.commit()


@router.post("/{notification_id}/read", status_code=204)
async def read_one(notification_id: int, session: SessionDep, staff: CurrentUser) -> None:
    if not await NotificationRepository(session).mark_read(staff.id, notification_id):
        raise HTTPException(404, "Notification not found")
    await session.commit()
