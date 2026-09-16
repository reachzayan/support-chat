from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.db import SessionDep
from app.models.site import Site
from app.security.deps import CurrentAdmin, CurrentUser
from app.services.site_admin import AdminError, SiteAdminService, build_snippet

router = APIRouter()


class SiteCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str | None = None
    name: str
    greeting: str
    privacy_url: str
    origins: list[str] | None = None
    website_url: str | None = None
    contact_info: list[str] | None = None


class SitePatchIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    greeting: str | None = None
    privacy_url: str | None = None
    origins: list[str] | None = None
    website_url: str | None = None
    contact_info: list[str] | None = None
    enabled: bool | None = None
    bot_enabled: bool | None = None
    human_enabled: bool | None = None
    callback_window_hours: int | None = None


class SiteOut(BaseModel):
    id: UUID
    key: str
    name: str
    greeting: str
    privacy_url: str
    public_key: str
    origins: list[str]
    snippet: str
    origins_missing_from_frame_ancestors: bool
    enabled: bool
    bot_enabled: bool
    human_enabled: bool
    callback_window_hours: int
    off_brand_blocklist: list[str]
    website_url: str | None
    widget_installed: bool | None
    widget_checked_at: datetime | None
    contact_info: list[str]


class OffBrandListIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[str]


class SiteListOut(BaseModel):
    items: list[SiteOut]
    frame_ancestors: list[str]
    widget_origin: str


def _http_error(exc: AdminError) -> HTTPException:
    if exc.code == "not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if exc.code == "conflict":
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflict")
    if exc.code == "invalid_origin":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid origin"
        )
    if exc.code == "too_large":
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Too large")
    if exc.code == "no_website_url":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Add a website URL before checking the install status.",
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid request"
    )


def _site_out(site: Site, ancestors: list[str], widget_origin: str) -> SiteOut:
    missing = any(origin not in ancestors for origin in site.allowed_origins)
    return SiteOut(
        id=site.id,
        key=site.key,
        name=site.name,
        greeting=site.greeting,
        privacy_url=site.privacy_url,
        public_key=site.public_key,
        origins=list(site.allowed_origins),
        snippet=build_snippet(site.key, site.public_key, widget_origin),
        origins_missing_from_frame_ancestors=missing,
        enabled=bool(getattr(site, "enabled", True)),
        bot_enabled=site.bot_enabled,
        human_enabled=site.human_enabled,
        callback_window_hours=int(getattr(site, "callback_window_hours", 24) or 24),
        off_brand_blocklist=list(site.off_brand_blocklist or []),
        website_url=site.website_url,
        widget_installed=site.widget_installed,
        widget_checked_at=site.widget_checked_at,
        contact_info=list(site.contact_info or []),
    )


@router.get("/api/sites", response_model=SiteListOut)
async def list_sites(session: SessionDep, _staff: CurrentUser) -> SiteListOut:
    sites, ancestors, widget_origin = await SiteAdminService(session).list_sites()
    return SiteListOut(
        items=[_site_out(site, ancestors, widget_origin) for site in sites],
        frame_ancestors=ancestors,
        widget_origin=widget_origin,
    )


@router.post("/api/sites", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(payload: SiteCreateIn, session: SessionDep, admin: CurrentAdmin) -> SiteOut:
    service = SiteAdminService(session)
    try:
        site = await service.create_site(
            key=payload.key,
            name=payload.name,
            greeting=payload.greeting,
            privacy_url=payload.privacy_url,
            origins=payload.origins,
            website_url=payload.website_url,
            contact_info=payload.contact_info,
            admin=admin,
        )
    except AdminError as exc:
        raise _http_error(exc) from exc
    _, ancestors, widget_origin = await service.list_sites()
    return _site_out(site, ancestors, widget_origin)


@router.patch("/api/sites/{site_id}", response_model=SiteOut)
async def patch_site(
    site_id: UUID, payload: SitePatchIn, session: SessionDep, _admin: CurrentAdmin
) -> Any:
    service = SiteAdminService(session)
    try:
        site = await service.update_site(
            site_id,
            name=payload.name,
            greeting=payload.greeting,
            privacy_url=payload.privacy_url,
            origins=payload.origins,
            website_url=payload.website_url,
            contact_info=payload.contact_info,
            enabled=payload.enabled,
            bot_enabled=payload.bot_enabled,
            human_enabled=payload.human_enabled,
            callback_window_hours=payload.callback_window_hours,
        )
    except AdminError as exc:
        raise _http_error(exc) from exc
    _, ancestors, widget_origin = await service.list_sites()
    return _site_out(site, ancestors, widget_origin)


@router.post("/api/sites/{site_id}/check-install", response_model=SiteOut)
async def check_install(site_id: UUID, session: SessionDep, _admin: CurrentAdmin) -> SiteOut:
    service = SiteAdminService(session)
    try:
        site = await service.check_install(site_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    _, ancestors, widget_origin = await service.list_sites()
    return _site_out(site, ancestors, widget_origin)


@router.delete("/api/sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(site_id: UUID, session: SessionDep, _admin: CurrentAdmin) -> None:
    try:
        await SiteAdminService(session).delete_site(site_id)
    except AdminError as exc:
        raise _http_error(exc) from exc


@router.patch("/api/sites/{site_id}/off-brand-list", response_model=SiteOut)
async def patch_off_brand_list(
    site_id: UUID, payload: OffBrandListIn, session: SessionDep, _admin: CurrentAdmin
) -> Any:
    service = SiteAdminService(session)
    try:
        site = await service.update_off_brand_list(site_id, payload.items)
    except AdminError as exc:
        raise _http_error(exc) from exc
    _, ancestors, widget_origin = await service.list_sites()
    return _site_out(site, ancestors, widget_origin)
