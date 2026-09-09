from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.chat.connection_manager import (
    AgentConnection,
    ConnectionManager,
    VisitorConnection,
    message_frame,
    state_frame,
)
from app.models.conversation import Conversation
from app.models.message import Message

ADA_DOT = "How fast are DOT results?"


def test_message_frame_includes_conversation_id() -> None:
    conversation_id = uuid4()
    message = Message(
        conversation_id=conversation_id,
        role="visitor",
        body=ADA_DOT,
        created_at=datetime(2026, 9, 9, 16, 0, tzinfo=UTC),
    )
    message.id = 40
    frame = message_frame(message)
    assert frame["type"] == "message"
    assert frame["body"] == ADA_DOT
    assert frame["conversation_id"] == str(conversation_id)
    assert frame["id"] == 40


def test_subscribe_keeps_prior_conversation_subscriptions() -> None:
    manager = ConnectionManager()
    websocket = SimpleNamespace()
    manager.register_agent(
        AgentConnection(
            websocket=websocket,
            user=SimpleNamespace(id=uuid4()),
            token_version=1,
            expires_at=datetime.now(UTC),
        )
    )
    first = uuid4()
    second = uuid4()
    manager.subscribe(websocket, first, 0)
    manager.subscribe(websocket, second, 3)
    agent = manager.agent_for(websocket)
    assert agent is not None
    assert set(agent.subscriptions) == {first, second}
    assert agent.subscriptions[first] == 0
    assert agent.subscriptions[second] == 3


def test_oldest_message_cursor_is_min_of_connected_sockets() -> None:
    manager = ConnectionManager()
    conversation_id = uuid4()
    visitor_socket = SimpleNamespace()
    agent_socket = SimpleNamespace()
    manager.register_visitor(
        VisitorConnection(
            websocket=visitor_socket,
            conversation_id=conversation_id,
            visitor_id=uuid4(),
            site_id=uuid4(),
            parent_origin="http://localhost:3000",
            last_event_id=12,
        )
    )
    manager.register_agent(
        AgentConnection(
            websocket=agent_socket,
            user=SimpleNamespace(id=uuid4()),
            token_version=1,
            expires_at=datetime.now(UTC),
        )
    )
    manager.subscribe(agent_socket, conversation_id, 8)
    assert manager.oldest_message_cursor(conversation_id) == 8


def test_oldest_message_cursor_is_none_when_nobody_is_listening() -> None:
    manager = ConnectionManager()
    assert manager.oldest_message_cursor(uuid4()) is None


def test_state_frame_includes_conversation_id() -> None:
    conversation_id = uuid4()
    conversation = Conversation(
        site_id=uuid4(),
        visitor_id=uuid4(),
        state="human",
    )
    conversation.id = conversation_id
    frame = state_frame(conversation, {"id": "agent", "display_name": "Alex Morgan"})
    assert frame["type"] == "state"
    assert frame["state"] == "human"
    assert frame["conversation_id"] == str(conversation_id)
