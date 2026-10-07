from typing import Annotated
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.notifications import Scenario
from app.db import SessionDep
from app.models.site import Site
from app.repositories.push_repo import PushRepository
from app.security.deps import CurrentUser
from app.services.push_content import preview_content
from app.services.web_push import decode_key, public_key, trusted_endpoint
from app.settings import Settings, get_settings

router = APIRouter(prefix="/api/notifications/push", tags=["push notifications"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


class EndpointIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(max_length=2048)

    @field_validator("endpoint")
    @classmethod
    def valid_endpoint(cls, value: str) -> str:
        return trusted_endpoint(value)


class KeysIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(max_length=100)
    auth: str = Field(max_length=32)

    @field_validator("p256dh")
    @classmethod
    def valid_public_key(cls, value: str) -> str:
        raw = decode_key(value)
        if len(raw) != 65 or raw[0] != 4:
            raise ValueError("Expected an uncompressed P-256 public key")
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
        return value

    @field_validator("auth")
    @classmethod
    def valid_auth(cls, value: str) -> str:
        if len(decode_key(value)) != 16:
            raise ValueError("Expected a 16-byte authentication secret")
        return value


class SubscriptionIn(EndpointIn):
    keys: KeysIn
    silent: bool = False


class SubscriptionOut(BaseModel):
    id: UUID


class ConfigOut(BaseModel):
    configured: bool
    public_key: str | None


class PreviewOut(BaseModel):
    title: str
    body: str
    action_label: str


class TestIn(EndpointIn):
    site_id: UUID | None = None
    scenario: Scenario = "needs_attention"


async def selected_preview(
    session: AsyncSession, site_id: UUID | None, scenario: Scenario
) -> dict[str, str]:
    site = await session.get(Site, site_id) if site_id else None
    if site_id and site is None:
        raise HTTPException(404, "Site not found")
    return preview_content(site.name if site else None, scenario)


@router.get("/preview", response_model=PreviewOut)
async def preview(
    session: SessionDep,
    staff: CurrentUser,
    site_id: UUID | None = None,
    scenario: Scenario = "needs_attention",
) -> PreviewOut:
    return PreviewOut.model_validate(await selected_preview(session, site_id, scenario))


@router.get("/config", response_model=ConfigOut)
async def config(staff: CurrentUser, settings: SettingsDep) -> ConfigOut:
    key = public_key(settings)
    return ConfigOut(configured=key is not None, public_key=key)


@router.post("/subscriptions", response_model=SubscriptionOut)
async def subscribe(
    payload: SubscriptionIn, session: SessionDep, staff: CurrentUser, settings: SettingsDep
) -> SubscriptionOut:
    if not public_key(settings):
        raise HTTPException(503, "Push notifications are not configured")
    try:
        device_id = await PushRepository(session).subscribe(
            staff, payload.endpoint, payload.keys.p256dh, payload.keys.auth, payload.silent
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    await session.commit()
    return SubscriptionOut(id=device_id)


@router.delete("/subscriptions", status_code=204)
async def unsubscribe(payload: EndpointIn, session: SessionDep, staff: CurrentUser) -> None:
    await PushRepository(session).unsubscribe(staff.id, payload.endpoint)
    await session.commit()


@router.post("/test", status_code=202)
async def test_push(payload: TestIn, session: SessionDep, staff: CurrentUser) -> None:
    content = await selected_preview(session, payload.site_id, payload.scenario)
    if not await PushRepository(session).test(staff.id, payload.endpoint, content):
        raise HTTPException(404, "Device is not subscribed")
    await session.commit()
