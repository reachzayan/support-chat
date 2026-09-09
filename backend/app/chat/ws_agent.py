import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.chat.connection_manager import FRAME_MAX, AgentConnection, connection_manager
from app.chat.state_machine import IllegalTransition
from app.db import session_maker
from app.repositories.user_repo import UserRepository
from app.security.jwt import decode_access_token
from app.services.conversation_service import CommandError, ConversationService
from app.settings import get_settings

router = APIRouter()


async def _idle_watch(websocket: WebSocket, last_seen: dict[str, float]) -> None:
    try:
        while True:
            await asyncio.sleep(5)
            idle = asyncio.get_running_loop().time() - last_seen["t"]
            if idle >= 30:
                await websocket.close(code=1001)
                return
            if idle >= 20:
                await websocket.send_json({"v": 1, "type": "ping"})
    except Exception:
        return


@router.websocket("/ws/agent")
async def agent_socket(websocket: WebSocket) -> None:
    settings = get_settings()
    origin = websocket.headers.get("origin")
    if origin != settings.staff_app_origin:
        await websocket.close(code=4403)
        return
    await websocket.accept()
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=5)
    except TimeoutError:
        await websocket.close(code=4401)
        return
    except WebSocketDisconnect:
        return
    if len(raw) > FRAME_MAX:
        await websocket.close(code=4401)
        return
    try:
        frame = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.close(code=4401)
        return
    if not isinstance(frame, dict) or frame.get("v") != 1 or frame.get("type") != "auth":
        await websocket.close(code=4401)
        return
    access_token = frame.get("access_token")
    if not isinstance(access_token, str):
        await websocket.close(code=4401)
        return
    try:
        payload = decode_access_token(access_token, settings)
        user_id = UUID(str(payload["sub"]))
        token_version = int(payload["token_version"])
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=UTC)
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        await websocket.close(code=4401)
        return
    async with session_maker()() as session:
        user = await UserRepository(session).get_by_id(user_id)
        if user is None or not user.is_active or user.token_version != token_version:
            await websocket.close(code=4401)
            return
        session.expunge(user)
    connection = AgentConnection(
        websocket=websocket,
        user=user,
        token_version=token_version,
        expires_at=expires_at,
    )
    connection_manager.register_agent(connection)
    closer = asyncio.create_task(_close_at_expiry(websocket, expires_at))
    try:
        await _agent_loop(websocket, connection)
    finally:
        closer.cancel()
        connection_manager.drop(websocket)


async def _close_agent(websocket: WebSocket, code: int) -> None:
    try:
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close(code=code)
    except Exception:
        return


async def _close_at_expiry(websocket: WebSocket, expires_at: datetime) -> None:
    delay = (expires_at - datetime.now(UTC)).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)
    await _close_agent(websocket, 4401)


async def _agent_loop(websocket: WebSocket, connection: AgentConnection) -> None:
    last_seen = {"t": asyncio.get_running_loop().time()}
    watcher = asyncio.create_task(_idle_watch(websocket, last_seen))
    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                return
            last_seen["t"] = asyncio.get_running_loop().time()
            if datetime.now(UTC) >= connection.expires_at:
                await _close_agent(websocket, 4401)
                return
            if len(raw) > FRAME_MAX:
                await connection_manager.send_error(websocket, "oversize")
                continue
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                await connection_manager.send_error(websocket, "invalid")
                continue
            if not isinstance(frame, dict):
                await connection_manager.send_error(websocket, "invalid")
                continue
            await _handle_agent_frame(websocket, connection, frame)
            if websocket.application_state != WebSocketState.CONNECTED:
                return
    finally:
        watcher.cancel()


async def _handle_agent_frame(
    websocket: WebSocket, connection: AgentConnection, frame: dict
) -> None:
    if frame.get("v") != 1:
        await connection_manager.send_error(websocket, "invalid")
        return
    frame_type = frame.get("type")
    if frame_type in {"pong", "ping"}:
        if not await _staff_still_valid(connection):
            await _close_agent(websocket, 4401)
            return
        if frame_type == "ping":
            await websocket.send_json({"v": 1, "type": "pong"})
        return
    if not await _staff_still_valid(connection):
        await _close_agent(websocket, 4401)
        return
    if frame_type == "subscribe":
        await _subscribe(websocket, frame)
        return
    if frame_type in {"join", "close_attention", "message", "end", "transfer_to_bot"}:
        await _run_agent_command(websocket, connection, frame_type, frame)
        return
    await connection_manager.send_error(websocket, "unknown_type")


async def _staff_still_valid(connection: AgentConnection) -> bool:
    async with session_maker()() as session:
        user = await UserRepository(session).get_by_id(connection.user.id)
        if user is None or not user.is_active or user.token_version != connection.token_version:
            return False
        session.expunge(user)
        connection.user = user
        return True


async def _subscribe(websocket: WebSocket, frame: dict) -> None:
    try:
        conversation_id = UUID(str(frame["conversation_id"]))
        last_event_id = int(frame.get("last_event_id") or 0)
    except (KeyError, ValueError, TypeError):
        await connection_manager.send_error(websocket, "invalid")
        return
    connection_manager.subscribe(websocket, conversation_id, last_event_id)
    await connection_manager.catch_up_socket(websocket)


async def _run_agent_command(
    websocket: WebSocket, connection: AgentConnection, kind: str, frame: dict
) -> None:
    try:
        conversation_id = UUID(str(frame["conversation_id"]))
    except (KeyError, ValueError, TypeError):
        await connection_manager.send_error(websocket, "invalid")
        return
    async with session_maker()() as session:
        service = ConversationService(session)
        try:
            if kind == "join":
                result = await service.join(conversation_id, connection.user)
            elif kind == "message":
                result = await service.agent_message(
                    conversation_id,
                    connection.user,
                    UUID(str(frame["client_message_id"])),
                    str(frame.get("body") or ""),
                )
            elif kind == "close_attention":
                result = await service.close_attention(conversation_id, connection.user)
            elif kind == "transfer_to_bot":
                result = await service.transfer_to_bot(conversation_id, connection.user)
            else:
                result = await service.end(conversation_id, connection.user)
        except CommandError as exc:
            await connection_manager.send_error(websocket, exc.code, **exc.extra)
            return
        except (IllegalTransition, ValueError, KeyError, TypeError):
            await connection_manager.send_error(websocket, "invalid")
            return
    if kind == "message" and result.message is not None and result.client_message_id:
        await connection_manager.send_ack(websocket, result.client_message_id, result.message.id)
    async with session_maker()() as session:
        assigned = await ConversationService(session).assigned_agent_view(result.conversation)
    await connection_manager.send_state(websocket, result.conversation, assigned)
    if not result.duplicate:
        await connection_manager.after_commit(
            result.conversation,
            result.site_key,
            result.message.id if result.message is not None else None,
        )
