import asyncio
import json
from uuid import UUID

import jwt
import structlog
from anyio import CancelScope
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.chat.connection_manager import FRAME_MAX, VisitorConnection, connection_manager
from app.chat.state_machine import IllegalTransition
from app.db import session_maker
from app.security.client_ip import request_client_ip
from app.security.surfaces import websocket_surface_allowed
from app.security.widget_tokens import decode_widget_token
from app.services.conversation_service import CommandError, ConversationService
from app.settings import get_settings

log = structlog.get_logger("ws_visitor")

router = APIRouter()
MAX_MESSAGE_ID = (1 << 63) - 1
IDLE_CHECK_SECONDS = 5.0
IDLE_PING_AFTER_SECONDS = 20.0
IDLE_CLOSE_SECONDS = 30.0
ORIGIN_RECHECK_SECONDS = 10.0
_bot_generation_tasks: set[asyncio.Task] = set()


async def stop_bot_generations() -> None:
    tasks = list(_bot_generation_tasks)
    for task in tasks:
        task.cancel()
    with CancelScope(shield=True):
        await asyncio.gather(*tasks, return_exceptions=True)


async def _idle_watch(websocket: WebSocket, last_seen: dict[str, float]) -> None:
    try:
        while True:
            await asyncio.sleep(IDLE_CHECK_SECONDS)
            idle = asyncio.get_running_loop().time() - last_seen["t"]
            if idle >= IDLE_CLOSE_SECONDS:
                await websocket.close(code=1001)
                return
            if idle >= IDLE_PING_AFTER_SECONDS:
                await websocket.send_json({"v": 1, "type": "ping"})
    except Exception:
        return


async def _conversation_idle_watch(websocket: WebSocket, connection: VisitorConnection) -> None:
    try:
        while True:
            await asyncio.sleep(15)
            if websocket.application_state != WebSocketState.CONNECTED:
                return
            if connection.conversation_id is None:
                continue
            async with session_maker()() as session:
                result = await ConversationService(session).tick_idle(connection.conversation_id)
            if result is None:
                continue
            async with session_maker()() as session:
                assigned = await ConversationService(session).assigned_agent_view(
                    result.conversation
                )
            await connection_manager.send_state(websocket, result.conversation, assigned)
            await connection_manager.after_commit(
                result.conversation,
                result.site_key,
                result.message.id if result.message is not None else None,
            )
    except Exception:
        return


@router.websocket("/ws/visitor")
async def visitor_socket(websocket: WebSocket) -> None:
    settings = get_settings()
    if websocket.headers.get("origin") != settings.widget_origin or not websocket_surface_allowed(
        websocket.headers.get("host"), settings.widget_origin, settings
    ):
        await websocket.close(code=4403)
        return
    await websocket.accept()
    connection = await _authenticate_visitor(websocket, settings)
    if connection is None:
        return
    connection_manager.register_visitor(connection)
    try:
        try:
            await connection_manager.catch_up_socket(
                websocket, last_event_id=connection.last_event_id
            )
        except Exception:
            await connection_manager.send_error(websocket, "unavailable")
            await websocket.close(code=1011)
            return
        await _visitor_loop(websocket, connection)
    finally:
        connection_manager.drop(websocket)


async def _authenticate_visitor(websocket: WebSocket, settings) -> VisitorConnection | None:
    frame = await _read_auth_frame(websocket)
    if frame is None:
        return None
    token = frame.get("bootstrap_token")
    parent_origin = frame.get("parent_origin")
    if not isinstance(token, str) or not isinstance(parent_origin, str):
        await websocket.close(code=4401)
        return None
    try:
        claims = decode_widget_token(token, settings)
    except jwt.ExpiredSignatureError:
        await websocket.close(code=4401)
        return None
    except jwt.InvalidTokenError:
        await websocket.close(code=4403)
        return None
    if claims.get("parent_origin") != parent_origin:
        await websocket.close(code=4403)
        return None
    last_event_id = frame.get("last_event_id", 0)
    if (
        not isinstance(last_event_id, int)
        or isinstance(last_event_id, bool)
        or not 0 <= last_event_id <= MAX_MESSAGE_ID
    ):
        await websocket.close(code=4401)
        return None
    site_id = UUID(str(claims["site_id"]))
    visitor_id = UUID(str(claims["visitor_id"]))
    parent = str(parent_origin)
    raw_conversation_id = claims.get("conversation_id")
    conversation_id = UUID(str(raw_conversation_id)) if raw_conversation_id else None
    async with session_maker()() as session:
        service = ConversationService(session)
        allowed = await service.parent_origin_allowed(site_id, parent)
        if allowed and conversation_id is None:
            conversation_id = await service.open_submitted_conversation_id(site_id, visitor_id)
    if not allowed:
        await websocket.close(code=4403)
        return None
    return VisitorConnection(
        websocket=websocket,
        conversation_id=conversation_id,
        visitor_id=visitor_id,
        site_id=site_id,
        parent_origin=parent,
        last_event_id=last_event_id,
        origin_checked_at=asyncio.get_running_loop().time(),
    )


async def _read_auth_frame(websocket: WebSocket) -> dict | None:
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=5)
    except TimeoutError:
        await websocket.close(code=4401)
        return None
    except WebSocketDisconnect:
        return None
    if len(raw) > FRAME_MAX:
        await websocket.close(code=4401)
        return None
    try:
        frame = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.close(code=4401)
        return None
    if not isinstance(frame, dict) or frame.get("v") != 1 or frame.get("type") != "auth":
        await websocket.close(code=4401)
        return None
    return frame


async def _visitor_loop(websocket: WebSocket, connection: VisitorConnection) -> None:
    last_seen = {"t": asyncio.get_running_loop().time()}
    watcher = asyncio.create_task(_idle_watch(websocket, last_seen))
    idle_nudge = asyncio.create_task(_conversation_idle_watch(websocket, connection))
    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                return
            last_seen["t"] = asyncio.get_running_loop().time()
            if len(raw) > FRAME_MAX:
                await connection_manager.send_error(websocket, "oversize")
                continue
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                log.info(
                    "malformed_frame",
                    conversation_id=str(connection.conversation_id),
                    role="visitor",
                    length=len(raw),
                )
                await connection_manager.send_error(websocket, "invalid")
                continue
            if not isinstance(frame, dict):
                await connection_manager.send_error(websocket, "invalid")
                continue
            await _handle_visitor_frame(websocket, connection, frame)
            if websocket.application_state != WebSocketState.CONNECTED:
                return
    finally:
        watcher.cancel()
        idle_nudge.cancel()
        with CancelScope(shield=True):
            await asyncio.gather(watcher, idle_nudge, return_exceptions=True)


async def _handle_visitor_ping_pong(
    websocket: WebSocket, connection: VisitorConnection, frame_type: str
) -> None:
    if not await _parent_still_allowed(websocket, connection, throttle=True):
        return
    if frame_type == "ping":
        await websocket.send_json({"v": 1, "type": "pong"})
    await connection_manager.catch_up_socket(websocket)


async def _handle_visitor_resume(
    websocket: WebSocket, connection: VisitorConnection, frame: dict
) -> None:
    cursor = frame.get("last_event_id")
    if not isinstance(cursor, int) or isinstance(cursor, bool) or not 0 <= cursor <= MAX_MESSAGE_ID:
        await connection_manager.send_error(websocket, "invalid")
        return
    if not await _parent_still_allowed(websocket, connection):
        return
    await connection_manager.catch_up_socket(websocket, last_event_id=cursor)


async def _handle_visitor_older(
    websocket: WebSocket, connection: VisitorConnection, frame: dict
) -> None:
    before_id = frame.get("before_id")
    if (
        not isinstance(before_id, int)
        or isinstance(before_id, bool)
        or not 1 <= before_id <= MAX_MESSAGE_ID
    ):
        await connection_manager.send_error(websocket, "invalid")
        return
    if not await _parent_still_allowed(websocket, connection):
        return
    if connection.conversation_id is None:
        await connection_manager.send_error(websocket, "invalid")
        return
    await connection_manager.send_older(websocket, connection.conversation_id, before_id)


async def _handle_visitor_frame(
    websocket: WebSocket, connection: VisitorConnection, frame: dict
) -> None:
    if frame.get("v") != 1:
        await connection_manager.send_error(websocket, "invalid")
        return
    frame_type = frame.get("type")
    if not isinstance(frame_type, str):
        await connection_manager.send_error(websocket, "invalid")
        return
    if frame_type in {"pong", "ping"}:
        await _handle_visitor_ping_pong(websocket, connection, frame_type)
        return
    if frame_type == "heartbeat":
        if not await _parent_still_allowed(websocket, connection, throttle=True):
            return
        await connection_manager.catch_up_socket(websocket)
        return
    if frame_type == "resume":
        await _handle_visitor_resume(websocket, connection, frame)
        return
    if frame_type == "older":
        await _handle_visitor_older(websocket, connection, frame)
        return
    if frame_type in {"hello", "prechat", "message", "escalate", "handoff_wait_response"}:
        await _run_visitor_command(websocket, connection, frame_type, frame)
        return
    await connection_manager.send_error(websocket, "unknown_type")


async def _parent_still_allowed(
    websocket: WebSocket, connection: VisitorConnection, *, throttle: bool = False
) -> bool:
    now = asyncio.get_running_loop().time()
    if throttle and (now - connection.origin_checked_at) < ORIGIN_RECHECK_SECONDS:
        return True
    async with session_maker()() as session:
        allowed = await ConversationService(session).parent_origin_allowed(
            connection.site_id, connection.parent_origin
        )
    if allowed:
        connection.origin_checked_at = now
        return True
    try:
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close(code=4403)
    except Exception:
        pass
    connection_manager.drop(websocket)
    return False


async def _deliver_visitor_result(
    websocket: WebSocket, connection: VisitorConnection, kind: str, result
) -> None:
    if kind == "prechat":
        connection.conversation_id = result.conversation.id
        connection.pending_hello = None
    assigned = None
    async with session_maker()() as session:
        assigned = await ConversationService(session).assigned_agent_view(result.conversation)
    # Deliver committed rows before the direct state frame so a later send
    # failure cannot drop the socket before the visitor sees new messages.
    if not result.duplicate:
        await connection_manager.after_commit(
            result.conversation,
            result.site_key,
            result.message.id if result.message is not None else None,
        )
        await connection_manager.catch_up_socket(websocket)
    await connection_manager.send_state(websocket, result.conversation, assigned)
    if kind == "prechat":
        await connection_manager.send_prechat_accepted(
            websocket,
            result.submission_id or "",
            result.message.id if result.message is not None else None,
        )
    elif kind == "message" and result.message is not None and result.client_message_id:
        await connection_manager.send_ack(websocket, result.client_message_id, result.message.id)
    elif kind == "handoff_wait_response":
        await websocket.send_json({"v": 1, "type": "handoff_wait_accepted"})
    if result.generation_id is not None:
        task = asyncio.create_task(_shielded_bot_generation(websocket, result))
        _bot_generation_tasks.add(task)
        task.add_done_callback(_bot_generation_tasks.discard)


async def _run_visitor_command(
    websocket: WebSocket, connection: VisitorConnection, kind: str, frame: dict
) -> None:
    async with session_maker()() as session:
        service = ConversationService(session)
        allowed = await service.parent_origin_allowed(connection.site_id, connection.parent_origin)
        if not allowed:
            await websocket.close(code=4403)
            return
        try:
            result = await _dispatch_visitor(
                service, connection, kind, frame, _socket_ip(websocket)
            )
        except CommandError as exc:
            if exc.code == "origin_revoked":
                await websocket.close(code=4403)
                return
            await connection_manager.send_error(websocket, exc.code, **exc.extra)
            return
        except (IllegalTransition, ValueError, KeyError, TypeError):
            await connection_manager.send_error(websocket, "invalid")
            return
        if result is None:
            return
    await _deliver_visitor_result(websocket, connection, kind, result)


async def _shielded_bot_generation(websocket: WebSocket, result) -> None:
    with CancelScope(shield=True):
        await _finish_bot_generation(websocket, result)


async def _finish_bot_generation(websocket: WebSocket, result) -> None:
    await connection_manager.send_typing(websocket, True)
    bot = None
    try:
        async with session_maker()() as session:
            bot = await ConversationService(session).run_bot_turn(
                result.conversation.id, result.generation_id
            )
    except Exception as exc:
        log.info(
            "bot_generation_failed",
            conversation_id=str(result.conversation.id),
            role="visitor",
            error_class=type(exc).__name__,
        )
    finally:
        await connection_manager.send_typing(websocket, False)
    if bot is None:
        return
    async with session_maker()() as session:
        assigned = await ConversationService(session).assigned_agent_view(bot.conversation)
    await connection_manager.send_state(websocket, bot.conversation, assigned)
    await connection_manager.after_commit(
        bot.conversation,
        bot.site_key,
        bot.message.id if bot.message is not None else None,
    )


def _socket_ip(websocket: WebSocket) -> str | None:
    settings = get_settings()
    peer = websocket.client.host if websocket.client else None
    return request_client_ip(peer, websocket.headers, settings)


async def _dispatch_visitor(
    service: ConversationService,
    connection: VisitorConnection,
    kind: str,
    frame: dict,
    client_ip: str | None,
):
    conversation_id = connection.conversation_id
    visitor_id = connection.visitor_id
    parent_origin = connection.parent_origin
    if kind == "hello":
        if conversation_id is None:
            connection.pending_hello = ConversationService.sanitize_hello_page(
                parent_origin,
                str(frame.get("page_url") or ""),
                str(frame.get("page_title") or ""),
                str(frame.get("referrer") or ""),
            )
            return None
        return await service.hello(
            conversation_id,
            visitor_id,
            parent_origin,
            str(frame.get("page_url") or ""),
            str(frame.get("page_title") or ""),
            str(frame.get("referrer") or ""),
        )
    if kind == "prechat":
        return await service.submit_prechat(
            conversation_id,
            visitor_id,
            parent_origin,
            UUID(str(frame["submission_id"])),
            str(frame.get("name") or ""),
            str(frame.get("email") or ""),
            str(frame.get("phone") or ""),
            str(frame.get("inquiry_type") or "other"),
            str(frame.get("message") or ""),
            client_ip,
            pending_hello=connection.pending_hello,
        )
    if conversation_id is None:
        raise CommandError("invalid")
    if kind == "message":
        return await service.visitor_message(
            conversation_id,
            visitor_id,
            parent_origin,
            UUID(str(frame["client_message_id"])),
            str(frame.get("body") or ""),
            client_ip,
        )
    if kind == "escalate":
        return await service.escalate(conversation_id, visitor_id, parent_origin)
    if kind == "handoff_wait_response":
        prompt_id = frame.get("prompt_id")
        choice = frame.get("choice")
        if (
            type(prompt_id) is not int
            or not 1 <= prompt_id <= MAX_MESSAGE_ID
            or choice not in ("wait", "end")
        ):
            raise CommandError("invalid")
        return await service.respond_handoff_wait(
            conversation_id, visitor_id, parent_origin, prompt_id, choice == "wait"
        )
    raise ValueError(kind)
