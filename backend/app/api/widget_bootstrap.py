import json
from hmac import compare_digest
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError

from app.chat.connection_manager import connection_manager, message_frame
from app.db import SessionDep
from app.security.client_ip import _as_ip, request_client_ip
from app.security.widget_tokens import create_widget_token
from app.services.conversation_service import CommandError, ConversationService
from app.services.conversation_types import BootstrapResult
from app.services.rate_limit import RateLimiter, RateLimitExceeded, RateLimitUnavailable
from app.services.site_admin import SiteAdminService
from app.settings import get_settings

router = APIRouter()
BOOTSTRAP_MAX_BYTES = 8192
FRAME_ANCESTORS_MAX_BYTES = 512


class BootstrapBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_key: str
    public_key: str
    resume_token: str | None = None
    action: Literal["identify", "history", "open", "refresh", "reset", "forget"] = "identify"
    conversation_id: UUID | None = None
    replace_current: bool = False


class FrameAncestorsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_key: str
    public_key: str
    parent_origin: str


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
    if exc.code == "active_chat_exists":
        return JSONResponse({"detail": "Active chat exists"}, status_code=409)
    return JSONResponse({"detail": "Invalid request"}, status_code=400)


def _private_json(body: dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        body,
        status_code=status_code,
        headers={"Cache-Control": "private, no-store"},
    )


def _service_secret_matches(request: Request, configured_secret: str) -> bool:
    supplied_secret = request.headers.get("x-supportchat-widget-csp", "")
    return bool(configured_secret) and compare_digest(
        configured_secret.encode("utf-8"), supplied_secret.encode("utf-8")
    )


def _bootstrap_response_body(result: BootstrapResult) -> dict[str, Any]:
    body: dict[str, Any] = {
        "mode": result.mode,
        "widget": {
            "name": result.site_name,
            "greeting": result.greeting,
            "privacy_url": result.privacy_url,
            "contact_info": result.contact_info,
            "bot_enabled": result.bot_enabled,
            "human_enabled": result.human_enabled,
        },
    }
    if result.mode == "conversation":
        assert result.visitor_id is not None
        assert result.conversation_id is not None
        assert result.conversation_state is not None
        body["bootstrap_token"] = create_widget_token(
            result.site_id,
            result.visitor_id,
            result.conversation_id,
            result.parent_origin,
            get_settings(),
        )
        body["conversation"] = {
            "id": str(result.conversation_id),
            "state": result.conversation_state,
            "assigned_agent": result.assigned_agent,
            "messages": [message_frame(message) for message in (result.messages or [])],
            "has_older": result.messages_has_older,
        }
    if result.identity is not None:
        body["identity"] = {
            "display_name": result.identity.display_name,
            "email_hint": result.identity.email_hint,
            "phone_hint": result.identity.phone_hint,
            "chat_count": result.identity.chat_count,
        }
    if result.conversations is not None:
        body["conversations"] = [
            {
                "id": str(conversation.id),
                "state": conversation.state,
                "inquiry_type": conversation.inquiry_type,
                "created_at": conversation.created_at.isoformat(),
                "last_message_at": conversation.last_message_at.isoformat(),
                "assigned_agent": conversation.assigned_agent,
                "is_current": conversation.is_current,
            }
            for conversation in result.conversations
        ]
    if result.resume_token is not None:
        body["resume_token"] = result.resume_token
    return body


async def _frame_ancestors_body(request: Request) -> FrameAncestorsBody | JSONResponse:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > FRAME_ANCESTORS_MAX_BYTES:
                return _private_json({"detail": "Invalid request"}, status_code=400)
        except ValueError:
            return _private_json({"detail": "Invalid request"}, status_code=400)
    raw = await request.body()
    if len(raw) > FRAME_ANCESTORS_MAX_BYTES:
        return _private_json({"detail": "Invalid request"}, status_code=400)
    try:
        return FrameAncestorsBody.model_validate(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        return _private_json({"detail": "Invalid request"}, status_code=400)


@router.post("/api/internal/widget-frame-ancestors", include_in_schema=False)
async def widget_frame_ancestors(request: Request, session: SessionDep) -> JSONResponse:
    settings = get_settings()
    if not _service_secret_matches(request, settings.widget_csp_service_secret):
        return _private_json({"detail": "Not found"}, status_code=404)

    payload = await _frame_ancestors_body(request)
    if isinstance(payload, JSONResponse):
        return payload

    client_ip = _as_ip(request.headers.get("x-supportchat-client-ip"))
    if not client_ip:
        client_ip = request.client.host if request.client else None
    try:
        await RateLimiter(settings).hit_widget_csp(
            client_ip,
            payload.site_key,
            payload.public_key,
        )
    except RateLimitExceeded:
        return _private_json({"detail": "Too many requests"}, status_code=429)
    except RateLimitUnavailable:
        return _private_json({"detail": "Unavailable"}, status_code=503)

    ancestors = await SiteAdminService(session).frame_ancestors_for_site(
        payload.site_key,
        payload.public_key,
        payload.parent_origin,
    )
    if ancestors is None:
        return _private_json({"detail": "Not found"}, status_code=404)
    return _private_json({"ancestors": ancestors})


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
    client_ip = request_client_ip(
        request.client.host if request.client else None,
        request.headers,
        settings,
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
            action=payload.action,
            conversation_id=payload.conversation_id,
            replace_current=payload.replace_current,
        )
    except CommandError as exc:
        return _command_error_response(exc)

    for conversation in result.changed_conversations:
        await connection_manager.after_commit(conversation, result.site_key, None)
    return JSONResponse(
        _bootstrap_response_body(result), headers=_cors_headers(result.parent_origin)
    )
