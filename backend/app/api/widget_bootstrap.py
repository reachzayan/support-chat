import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError

from app.db import SessionDep
from app.security.client_ip import resolve_client_ip
from app.security.widget_tokens import create_widget_token
from app.services.conversation_service import CommandError, ConversationService
from app.services.rate_limit import RateLimiter, RateLimitExceeded, RateLimitUnavailable
from app.services.site_admin import SiteAdminService
from app.settings import get_settings

router = APIRouter()
BOOTSTRAP_MAX_BYTES = 8192


class BootstrapBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_key: str
    public_key: str
    resume_token: str | None = None


def _cors_headers(origin: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin,
        "Vary": "Origin",
        "Cache-Control": "no-store",
    }


def _command_error_response(exc: CommandError) -> JSONResponse:
    if exc.code == "not_found":
        return JSONResponse({"detail": "Not found"}, status_code=404)
    if exc.code == "forbidden":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    if exc.code == "rate_limited":
        return JSONResponse({"detail": "Too many requests"}, status_code=429)
    if exc.code == "unavailable":
        return JSONResponse({"detail": "Unavailable"}, status_code=503)
    return JSONResponse({"detail": "Invalid request"}, status_code=400)


@router.get("/api/public/widget-frame-ancestors")
async def widget_frame_ancestors(
    request: Request, session: SessionDep, parent: str | None = None
) -> JSONResponse:
    raw = parent or request.headers.get("referer")
    ancestors = await SiteAdminService(session).frame_ancestors_for_parent(raw)
    return JSONResponse(
        {"ancestors": ancestors},
        headers={"Cache-Control": "private, max-age=15", "Vary": "Referer"},
    )


@router.post("/api/public/widget-bootstrap")
async def widget_bootstrap(request: Request, session: SessionDep) -> JSONResponse:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > BOOTSTRAP_MAX_BYTES:
                return JSONResponse({"detail": "Invalid request"}, status_code=400)
        except ValueError:
            return JSONResponse({"detail": "Invalid request"}, status_code=400)
    raw = await request.body()
    if len(raw) > BOOTSTRAP_MAX_BYTES:
        return JSONResponse({"detail": "Invalid request"}, status_code=400)
    try:
        payload = BootstrapBody.model_validate(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        return JSONResponse({"detail": "Invalid request"}, status_code=400)

    origin = request.headers.get("origin")
    settings = get_settings()
    client_ip = resolve_client_ip(
        request.client.host if request.client else None,
        request.headers,
        [part.strip() for part in settings.trusted_proxy_cidrs.split(",") if part.strip()],
    )
    try:
        await RateLimiter(settings).hit_bootstrap(client_ip, payload.site_key)
    except RateLimitExceeded:
        return JSONResponse({"detail": "Too many requests"}, status_code=429)
    except RateLimitUnavailable:
        return JSONResponse({"detail": "Unavailable"}, status_code=503)
    service = ConversationService(session)
    try:
        result = await service.bootstrap(
            site_key=payload.site_key,
            public_key=payload.public_key,
            origin_header=origin,
            resume_token=payload.resume_token,
            client_host=client_ip,
            user_agent=request.headers.get("user-agent"),
        )
    except CommandError as exc:
        return _command_error_response(exc)

    settings = get_settings()
    token = create_widget_token(
        result.site_id,
        result.visitor_id,
        result.conversation_id,
        result.parent_origin,
        settings,
    )
    body: dict[str, Any] = {
        "widget": {
            "name": result.site_name,
            "greeting": result.greeting,
            "privacy_url": result.privacy_url,
            "contact_info": result.contact_info,
            "bot_enabled": result.bot_enabled,
            "human_enabled": result.human_enabled,
        },
        "bootstrap_token": token,
    }
    if result.resume_token is not None:
        body["resume_token"] = result.resume_token
    return JSONResponse(body, headers=_cors_headers(result.parent_origin))
