from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session_maker
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.conversation_service import ConversationService

log = structlog.get_logger("chat")
FRAME_MAX = 16384


@dataclass
class VisitorConnection:
    websocket: WebSocket
    conversation_id: UUID
    visitor_id: UUID
    site_id: UUID
    parent_origin: str
    last_event_id: int = 0


@dataclass
class AgentConnection:
    websocket: WebSocket
    user: User
    token_version: int
    expires_at: datetime
    subscriptions: dict[UUID, int] = field(default_factory=dict)


class ConnectionManager:
    def __init__(self) -> None:
        self.suppress_wakeups = False
        self._visitors: dict[int, VisitorConnection] = {}
        self._agents: dict[int, AgentConnection] = {}

    def reset(self) -> None:
        self.suppress_wakeups = False
        self._visitors.clear()
        self._agents.clear()

    def register_visitor(self, connection: VisitorConnection) -> None:
        self._visitors[id(connection.websocket)] = connection

    def register_agent(self, connection: AgentConnection) -> None:
        self._agents[id(connection.websocket)] = connection

    def drop(self, websocket: WebSocket) -> None:
        self._visitors.pop(id(websocket), None)
        self._agents.pop(id(websocket), None)

    def visitor_for(self, websocket: WebSocket) -> VisitorConnection | None:
        return self._visitors.get(id(websocket))

    def agent_for(self, websocket: WebSocket) -> AgentConnection | None:
        return self._agents.get(id(websocket))

    def subscribe(self, websocket: WebSocket, conversation_id: UUID, last_event_id: int) -> None:
        agent = self.agent_for(websocket)
        if agent is None:
            return
        agent.subscriptions[conversation_id] = last_event_id

    def oldest_message_cursor(self, conversation_id: UUID) -> int | None:
        cursors: list[int] = []
        for visitor in self._visitors.values():
            if visitor.conversation_id == conversation_id:
                cursors.append(visitor.last_event_id)
        for agent in self._agents.values():
            cursor = agent.subscriptions.get(conversation_id)
            if cursor is not None:
                cursors.append(cursor)
        if not cursors:
            return None
        return min(cursors)

    async def catch_up_socket(
        self, websocket: WebSocket, *, last_event_id: int | None = None
    ) -> None:
        visitor = self.visitor_for(websocket)
        if visitor is not None:
            if last_event_id is not None:
                visitor.last_event_id = last_event_id
            await self._replay_visitor(visitor)
            return
        agent = self.agent_for(websocket)
        if agent is None:
            return
        conversation_ids = list(agent.subscriptions)
        async with session_maker()() as session:
            service = ConversationService(session)
            for conversation_id in conversation_ids:
                cursor = (
                    last_event_id
                    if last_event_id is not None
                    else agent.subscriptions[conversation_id]
                )
                await self._replay_agent_conversation(
                    agent, service, session, conversation_id, cursor
                )

    async def deliver_wakeup(self, payload: dict[str, Any]) -> None:
        if self.suppress_wakeups:
            return
        conversation_id = UUID(str(payload["conversation_id"]))
        site_key = str(payload.get("site_key") or "")
        await self._catch_up_conversation(conversation_id, site_key=site_key, inbox=True)

    async def after_commit(
        self,
        conversation: Conversation,
        site_key: str,
        last_message_id: int | None,
    ) -> None:
        payload = {
            "conversation_id": str(conversation.id),
            "state": conversation.state,
            "site_key": site_key,
            "last_message_id": last_message_id,
        }
        from app.chat.fanout import publish_wakeup

        await publish_wakeup(payload)
        await self.deliver_wakeup(payload)

    async def send_error(self, websocket: WebSocket, code: str, **extra: Any) -> None:
        frame = {"v": 1, "type": "error", "code": code, **extra}
        await self._send(websocket, frame)

    async def send_ack(self, websocket: WebSocket, client_message_id: str, message_id: int) -> None:
        await self._send(
            websocket,
            {"v": 1, "type": "ack", "client_message_id": client_message_id, "id": message_id},
        )

    async def send_prechat_accepted(
        self, websocket: WebSocket, submission_id: str, message_id: int | None
    ) -> None:
        await self._send(
            websocket,
            {
                "v": 1,
                "type": "prechat_accepted",
                "submission_id": submission_id,
                "message_id": message_id,
            },
        )

    async def send_state(
        self, websocket: WebSocket, conversation: Conversation, assigned: dict | None
    ) -> None:
        await self._send(websocket, state_frame(conversation, assigned))

    async def send_typing(self, websocket: WebSocket, active: bool) -> None:
        await self._send(websocket, {"v": 1, "type": "typing", "active": active})

    async def _catch_up_conversation(
        self, conversation_id: UUID, *, site_key: str, inbox: bool
    ) -> None:
        after = self.oldest_message_cursor(conversation_id)
        async with session_maker()() as session:
            service = ConversationService(session)
            try:
                messages, conversation = await service.replay(conversation_id, after)
            except Exception:
                log.info(
                    "wakeup_catch_up_failed",
                    conversation_id=str(conversation_id),
                    role="system",
                    length=0,
                )
                return
            assigned = await service.assigned_agent_view(conversation)
            await self._fanout_visitors(service, conversation, messages, assigned)
            await self._fanout_agents(
                UserRepository(session), conversation, messages, assigned, site_key, inbox
            )

    async def _fanout_visitors(
        self,
        service: ConversationService,
        conversation: Conversation,
        messages: list[Message],
        assigned: dict | None,
    ) -> None:
        for visitor in list(self._visitors.values()):
            if visitor.conversation_id != conversation.id:
                continue
            allowed = await service.parent_origin_allowed(visitor.site_id, visitor.parent_origin)
            if not allowed:
                try:
                    await visitor.websocket.close(code=4403)
                except Exception:
                    pass
                self.drop(visitor.websocket)
                continue
            await self._send_new_messages(visitor.websocket, messages, visitor.last_event_id)
            if messages:
                visitor.last_event_id = max(visitor.last_event_id, messages[-1].id)
            await self.send_state(visitor.websocket, conversation, assigned)

    async def _fanout_agents(
        self,
        users: UserRepository,
        conversation: Conversation,
        messages: list[Message],
        assigned: dict | None,
        site_key: str,
        inbox: bool,
    ) -> None:
        for agent in list(self._agents.values()):
            staff = await users.get_by_id(agent.user.id)
            if staff is None or not staff.is_active or staff.token_version != agent.token_version:
                try:
                    await agent.websocket.close(code=4401)
                except Exception:
                    pass
                self.drop(agent.websocket)
                continue
            if inbox:
                await self._send(
                    agent.websocket,
                    inbox_frame(conversation.id, conversation.state, site_key),
                )
            cursor = agent.subscriptions.get(conversation.id)
            if cursor is None:
                continue
            await self._send_new_messages(agent.websocket, messages, cursor)
            if messages:
                agent.subscriptions[conversation.id] = max(cursor, messages[-1].id)
            await self.send_state(agent.websocket, conversation, assigned)

    async def _replay_visitor(self, visitor: VisitorConnection) -> None:
        async with session_maker()() as session:
            service = ConversationService(session)
            messages, conversation = await service.replay(
                visitor.conversation_id, visitor.last_event_id
            )
            assigned = await service.assigned_agent_view(conversation)
            await self._send_new_messages(visitor.websocket, messages, visitor.last_event_id)
            if messages:
                visitor.last_event_id = messages[-1].id
            await self.send_state(visitor.websocket, conversation, assigned)

    async def _replay_agent_conversation(
        self,
        agent: AgentConnection,
        service: ConversationService,
        session: AsyncSession,
        conversation_id: UUID,
        cursor: int,
    ) -> None:
        try:
            messages, conversation = await service.replay(conversation_id, cursor)
        except Exception:
            return
        assigned = await service.assigned_agent_view(conversation)
        await self._send_new_messages(agent.websocket, messages, cursor)
        if messages:
            agent.subscriptions[conversation_id] = messages[-1].id
        else:
            agent.subscriptions[conversation_id] = cursor
        await self.send_state(agent.websocket, conversation, assigned)

    async def _send_new_messages(
        self, websocket: WebSocket, messages: list[Message], cursor: int
    ) -> None:
        for message in messages:
            if message.id <= cursor:
                continue
            await self._send(websocket, message_frame(message))

    async def _send(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await websocket.send_json(payload)
        except Exception:
            self.drop(websocket)


def message_frame(message: Message) -> dict[str, Any]:
    source_ids = None
    if message.source_chunk_ids is not None:
        source_ids = [str(item) for item in message.source_chunk_ids]
    elif message.source_article_ids is not None:
        source_ids = [str(item) for item in message.source_article_ids]
    created = message.created_at.isoformat() if message.created_at is not None else ""
    return {
        "v": 1,
        "type": "message",
        "id": message.id,
        "conversation_id": str(message.conversation_id),
        "role": message.role,
        "body": message.body,
        "source_article_ids": source_ids,
        "source_chunk_ids": (
            [str(item) for item in message.source_chunk_ids]
            if message.source_chunk_ids is not None
            else None
        ),
        "source_urls": list(message.source_urls) if message.source_urls is not None else None,
        "display_locator": message.display_locator,
        "source_title": message.source_title,
        "system_reason": message.system_reason,
        "response_outcome": message.response_outcome,
        "reason_code": message.response_reason_code,
        "citations": [
            {
                "chunk_id": str(citation.chunk_id) if citation.chunk_id is not None else None,
                "snapshot_id": (
                    str(citation.snapshot_id) if citation.snapshot_id is not None else None
                ),
                "response_start": citation.response_start,
                "response_end": citation.response_end,
                "source_start": citation.source_start,
                "source_end": citation.source_end,
                "cited_text": citation.cited_text,
                "source_title": citation.source_title,
                "source_url": citation.source_url,
            }
            for citation in message.citations
        ],
        "created_at": created,
    }


def state_frame(conversation: Conversation, assigned: dict | None) -> dict[str, Any]:
    return {
        "v": 1,
        "type": "state",
        "conversation_id": str(conversation.id),
        "state": conversation.state,
        "assigned_agent": assigned,
    }


def inbox_frame(conversation_id: UUID, state: str, site_key: str) -> dict[str, Any]:
    return {
        "v": 1,
        "type": "inbox_upsert",
        "conversation_id": str(conversation_id),
        "state": state,
        "site_key": site_key,
    }


connection_manager = ConnectionManager()
