import re
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from app.db import SessionDep
from app.models.user import User
from app.security.client_ip import resolve_client_ip
from app.security.cookies import (
    REFRESH_COOKIE,
    clear_session_cookies,
    set_csrf_cookie,
    set_refresh_cookie,
)
from app.security.csrf import new_csrf_token, require_csrf
from app.security.deps import CurrentUser
from app.services.auth_service import AuthFailed, AuthService
from app.services.rate_limit import RateLimiter, RateLimitExceeded, RateLimitUnavailable
from app.settings import Settings, get_settings

router = APIRouter()
log = structlog.get_logger("auth")
LOGIN_FAILURE = "Invalid email or password"


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_has_local_and_domain(cls, value: str) -> str:
        trimmed = value.strip()
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", trimmed) is None:
            raise ValueError("invalid email")
        return trimmed


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=15)


class UserOut(BaseModel):
    id: UUID
    email: str
    display_name: str
    is_admin: bool


class SessionOut(BaseModel):
    access_token: str
    user: UserOut


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
    )


def _attach_session(response: Response, refresh_token: str, settings: Settings) -> None:
    set_refresh_cookie(response, refresh_token, settings)
    set_csrf_cookie(response, new_csrf_token(), settings)


def _request_ip(request: Request, settings: Settings) -> str | None:
    return resolve_client_ip(
        request.client.host if request.client else None,
        request.headers,
        [part.strip() for part in settings.trusted_proxy_cidrs.split(",") if part.strip()],
    )


async def _enforce_login_budget(request: Request, settings: Settings, email: str) -> None:
    limiter = RateLimiter(settings)
    ip = _request_ip(request, settings)
    try:
        await limiter.guard_login(email, ip)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        ) from exc
    except RateLimitUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unavailable"
        ) from exc


async def _record_login_failure(request: Request, settings: Settings, email: str) -> None:
    limiter = RateLimiter(settings)
    ip = _request_ip(request, settings)
    try:
        await limiter.hit_login_failure(email, ip)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        ) from exc
    except RateLimitUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unavailable"
        ) from exc


@router.post("/login", response_model=SessionOut)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionOut:
    await _enforce_login_budget(request, settings, payload.email)
    service = AuthService(session, settings)
    try:
        issued = await service.login(payload.email, payload.password)
    except AuthFailed:
        await _record_login_failure(request, settings, payload.email)
        log.info("login_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILURE
        ) from None
    _attach_session(response, issued.refresh_token, settings)
    return SessionOut(access_token=issued.access_token, user=_user_out(issued.user))


@router.post("/refresh", response_model=SessionOut)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionOut:
    require_csrf(request)
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        issued = await AuthService(session, settings).refresh(raw)
    except AuthFailed:
        clear_session_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        ) from None
    _attach_session(response, issued.refresh_token, settings)
    return SessionOut(access_token=issued.access_token, user=_user_out(issued.user))


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    require_csrf(request)
    await AuthService(session, settings).logout(request.cookies.get(REFRESH_COOKIE))
    clear_session_cookies(response)
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    return _user_out(current_user)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: CurrentUser,
) -> dict[str, str]:
    require_csrf(request)
    try:
        await AuthService(session, settings).change_password(
            current_user,
            payload.current_password,
            payload.new_password,
        )
    except AuthFailed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILURE
        ) from None
    return {"status": "ok"}
