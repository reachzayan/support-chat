import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.display_citations import visitor_citation_payloads
from app.db import session_maker
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.repositories.message_repo import MessageRepository
from app.repositories.user_repo import UserRepository
from app.services.conversation_service import ConversationService
from app.settings import get_settings

log = structlog.get_logger("chat")
FRAME_MAX = 16384
SEND_TIMEOUT = 3.0


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
        self._send_locks: dict[int, asyncio.Lock] = {}

    def reset(self) -> None:
        self.suppress_wakeups = False
        self._visitors.clear()
        self._agents.clear()
        self._send_locks.clear()

    def register_visitor(self, connection: VisitorConnection) -> None:
        self._visitors[id(connection.websocket)] = connection
        self._send_locks[id(connection.websocket)] = asyncio.Lock()

    def register_agent(self, connection: AgentConnection) -> None:
        self._agents[id(connection.websocket)] = connection
        self._send_locks[id(connection.websocket)] = asyncio.Lock()

    def drop(self, websocket: WebSocket) -> None:
        self._visitors.pop(id(websocket), None)
        self._agents.pop(id(websocket), None)
        self._send_locks.pop(id(websocket), None)

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

    async def send_older(self, websocket: WebSocket, conversation_id: UUID, before_id: int) -> None:
        async with session_maker()() as session:
            messages, has_older = await MessageRepository(session).list_before(
                conversation_id, before_id
            )
        await self._send(
            websocket,
            {
                "v": 1,
                "type": "history_page",
                "messages": [message_frame(message) for message in messages],
                "has_older": has_older,
            },
        )

    async def _catch_up_conversation(
        self, conversation_id: UUID, *, site_key: str, inbox: bool
    ) -> None:
        after = self.oldest_message_cursor(conversation_id)
        limit = get_settings().message_replay_limit
        try:
            while True:
                async with session_maker()() as session:
                    service = ConversationService(session)
                    messages, conversation = await service.replay(conversation_id, after)
                    assigned = await service.assigned_agent_view(conversation)
                    visitors = [
                        (
                            visitor,
                            await service.parent_origin_allowed(
                                visitor.site_id, visitor.parent_origin
                            ),
                        )
                        for visitor in list(self._visitors.values())
                        if visitor.conversation_id == conversation.id
                    ]
                    users = UserRepository(session)
                    agents = []
                    for agent in list(self._agents.values()):
                        staff = await users.get_by_id(agent.user.id)
                        agents.append(
                            (
                                agent,
                                bool(
                                    staff is not None
                                    and staff.is_active
                                    and staff.token_version == agent.token_version
                                ),
                            )
                        )
                await asyncio.gather(
                    *(
                        self._fanout_visitor(visitor, allowed, conversation, messages, assigned)
                        for visitor, allowed in visitors
                    ),
                    *(
                        self._fanout_agent(
                            agent, valid, conversation, messages, assigned, site_key, inbox
                        )
                        for agent, valid in agents
                    ),
                )
                if not messages or len(messages) < limit:
                    break
                after = messages[-1].id
        except Exception:
            log.info(
                "wakeup_catch_up_failed",
                conversation_id=str(conversation_id),
                role="system",
                length=0,
            )

    async def _fanout_visitor(
        self,
        visitor: VisitorConnection,
        allowed: bool,
        conversation: Conversation,
        messages: list[Message],
        assigned: dict | None,
    ) -> None:
        if not allowed:
            try:
                await visitor.websocket.close(code=4403)
            except Exception:
                pass
            self.drop(visitor.websocket)
            return
        delivered = await self._send_new_messages(
            visitor.websocket, messages, visitor.last_event_id
        )
        visitor.last_event_id = max(visitor.last_event_id, delivered)
        await self.send_state(visitor.websocket, conversation, assigned)

    async def _fanout_agent(
        self,
        agent: AgentConnection,
        valid: bool,
        conversation: Conversation,
        messages: list[Message],
        assigned: dict | None,
        site_key: str,
        inbox: bool,
    ) -> None:
        if not valid:
            try:
                await agent.websocket.close(code=4401)
            except Exception:
                pass
            self.drop(agent.websocket)
            return
        if inbox:
            await self._send(
                agent.websocket,
                inbox_frame(conversation.id, conversation.state, site_key),
            )
        cursor = agent.subscriptions.get(conversation.id)
        if cursor is None:
            return
        delivered = await self._send_new_messages(agent.websocket, messages, cursor)
        agent.subscriptions[conversation.id] = max(
            agent.subscriptions.get(conversation.id, cursor), delivered
        )
        await self.send_state(agent.websocket, conversation, assigned)

    async def _replay_visitor(self, visitor: VisitorConnection) -> None:
        limit = get_settings().message_replay_limit
        async with session_maker()() as session:
            service = ConversationService(session)
            cursor = visitor.last_event_id
            while True:
                messages, conversation = await service.replay(visitor.conversation_id, cursor)
                assigned = await service.assigned_agent_view(conversation)
                await session.close()
                delivered = await self._send_new_messages(
                    visitor.websocket, messages, visitor.last_event_id
                )
                visitor.last_event_id = max(visitor.last_event_id, delivered)
                cursor = visitor.last_event_id
                if self.visitor_for(visitor.websocket) is None:
                    break
                await self.send_state(visitor.websocket, conversation, assigned)
                if not messages or len(messages) < limit:
                    break

    async def _replay_agent_conversation(
        self,
        agent: AgentConnection,
        service: ConversationService,
        session: AsyncSession,
        conversation_id: UUID,
        cursor: int,
    ) -> None:
        limit = get_settings().message_replay_limit
        try:
            while True:
                messages, conversation = await service.replay(conversation_id, cursor)
                assigned = await service.assigned_agent_view(conversation)
                await session.close()
                delivered = await self._send_new_messages(agent.websocket, messages, cursor)
                agent.subscriptions[conversation_id] = max(
                    agent.subscriptions.get(conversation_id, cursor), delivered
                )
                cursor = agent.subscriptions[conversation_id]
                if self.agent_for(agent.websocket) is None:
                    break
                await self.send_state(agent.websocket, conversation, assigned)
                if not messages or len(messages) < limit:
                    break
        except Exception:
            return

    async def _send_new_messages(
        self, websocket: WebSocket, messages: list[Message], cursor: int
    ) -> int:
        for message in messages:
            if message.id <= cursor:
                continue
            if not await self._send(websocket, message_frame(message)):
                break
            cursor = message.id
        return cursor

    async def _send(self, websocket: WebSocket, payload: dict[str, Any]) -> bool:
        try:
            lock = self._send_locks.get(id(websocket))
            if lock is None:
                return False
            async with lock:
                if self._send_locks.get(id(websocket)) is not lock:
                    return False
                await asyncio.wait_for(websocket.send_json(payload), timeout=SEND_TIMEOUT)
            return True
        except Exception:
            self.drop(websocket)
            try:
                await asyncio.wait_for(websocket.close(code=1011), timeout=SEND_TIMEOUT)
            except Exception:
                pass
            return False


def message_frame(message: Message) -> dict[str, Any]:
    source_ids = None
    if message.source_chunk_ids is not None:
        source_ids = [str(item) for item in message.source_chunk_ids]
    elif message.source_article_ids is not None:
        source_ids = [str(item) for item in message.source_article_ids]
    created = message.created_at.isoformat() if message.created_at is not None else ""
    chips = visitor_citation_payloads(
        citations=list(message.citations or []),
        source_urls=list(message.source_urls) if message.source_urls is not None else None,
        source_title=message.source_title,
    )
    source_urls = [str(chip["source_url"]) for chip in chips if chip["source_url"]]
    source_title = chips[0]["source_title"] if chips else message.source_title
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
        "source_urls": source_urls or None,
        "display_locator": None,
        "source_title": source_title,
        "system_reason": message.system_reason,
        "response_outcome": message.response_outcome,
        "reason_code": message.response_reason_code,
        "citations": chips,
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
