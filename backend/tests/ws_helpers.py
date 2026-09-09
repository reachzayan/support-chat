import json
import uuid
from collections.abc import Callable, Iterator
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.site import Site
from app.models.user import User
from app.models.visitor import Visitor
from app.security.passwords import hash_password
from tests.conftest import TEST_DATABASE_URL

HOST_ORIGIN = "http://localhost:3000"
WIDGET_ORIGIN = "http://widget.localhost:3000"
STAFF_ORIGIN = "http://localhost:3000"
EVIL_ORIGIN = "http://evil.test"

DEMO_SITE_KEY = "demo"
DEMO_PUBLIC_KEY = "d" * 64
EASY_SITE_KEY = "samplesite"
EASY_PUBLIC_KEY = "e" * 64
BG_SITE_KEY = "backgroundchecks"
BG_PUBLIC_KEY = "b" * 64

DEMO_NAME = "SupportChat demo"
DEMO_GREETING = "Talk to a specialist about screening."
DEMO_PRIVACY = "http://localhost:3000/privacy"

ALEX_EMAIL = "agent@example.local"
ALEX_NAME = "Alex Morgan"
ALEX_PASSWORD = "secret"
JORDAN_EMAIL = "jordan@example.local"
JORDAN_NAME = "Jordan Lee"
JORDAN_PASSWORD = "secret"

DOT_QUESTION = "How fast are DOT results?"
AGENT_HELP = "I can help with that."
STILL_THERE = "still there?"
PRECHAT_SUBMISSION_ID = "10000000-0000-4000-8000-000000000001"
VISITOR_MESSAGE_ID = "10000000-0000-4000-8000-000000000002"
AGENT_MESSAGE_ID = "20000000-0000-4000-8000-000000000001"
JOIN_LINE_ALEX = "You're now chatting with Alex Morgan."

SYNC_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def sync_session() -> Iterator[Session]:
    engine = create_engine(SYNC_URL)
    factory = sessionmaker(engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def insert_site(
    key: str,
    name: str,
    public_key: str,
    allowed_origins: list[str] | None = None,
) -> uuid.UUID:
    session = next(sync_session())
    try:
        site = Site(
            key=key,
            name=name,
            public_key=public_key,
            allowed_origins=allowed_origins or [HOST_ORIGIN],
            greeting=DEMO_GREETING,
            privacy_url=DEMO_PRIVACY,
        )
        session.add(site)
        session.commit()
        session.refresh(site)
        return site.id
    finally:
        session.close()


def insert_staff(email: str, display_name: str, password: str) -> uuid.UUID:
    session = next(sync_session())
    try:
        user = User(
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
            is_admin=False,
            is_active=True,
            token_version=0,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id
    finally:
        session.close()


def seed_demo_world() -> tuple[uuid.UUID, uuid.UUID]:
    site_id = insert_site(DEMO_SITE_KEY, DEMO_NAME, DEMO_PUBLIC_KEY)
    alex_id = insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    return site_id, alex_id


def visitor_count(site_id: uuid.UUID | None = None) -> int:
    session = next(sync_session())
    try:
        query = select(func.count()).select_from(Visitor)
        if site_id is not None:
            query = query.where(Visitor.site_id == site_id)
        return int(session.scalar(query) or 0)
    finally:
        session.close()


def conversation_count(*, visitor_id: uuid.UUID | None = None, open_only: bool = False) -> int:
    session = next(sync_session())
    try:
        query = select(func.count()).select_from(Conversation)
        if visitor_id is not None:
            query = query.where(Conversation.visitor_id == visitor_id)
        if open_only:
            query = query.where(Conversation.state != "closed")
        return int(session.scalar(query) or 0)
    finally:
        session.close()


def open_conversations_for_visitor(visitor_id: uuid.UUID) -> list[Conversation]:
    session = next(sync_session())
    try:
        return list(
            session.scalars(
                select(Conversation).where(
                    Conversation.visitor_id == visitor_id,
                    Conversation.state != "closed",
                )
            ).all()
        )
    finally:
        session.close()


def message_count(
    conversation_id: uuid.UUID | None = None,
    *,
    role: str | None = None,
    body: str | None = None,
) -> int:
    session = next(sync_session())
    try:
        query = select(func.count()).select_from(Message)
        if conversation_id is not None:
            query = query.where(Message.conversation_id == conversation_id)
        if role is not None:
            query = query.where(Message.role == role)
        if body is not None:
            query = query.where(Message.body == body)
        return int(session.scalar(query) or 0)
    finally:
        session.close()


def bot_row_count() -> int:
    return message_count(role="bot")


def conversation_state(conversation_id: uuid.UUID) -> str:
    session = next(sync_session())
    try:
        convo = session.get(Conversation, conversation_id)
        assert convo is not None
        return convo.state
    finally:
        session.close()


def assigned_agent_id(conversation_id: uuid.UUID) -> uuid.UUID | None:
    session = next(sync_session())
    try:
        convo = session.get(Conversation, conversation_id)
        assert convo is not None
        return convo.assigned_agent_id
    finally:
        session.close()


def visitor_contact(visitor_id: uuid.UUID) -> tuple[str | None, str | None, str | None]:
    session = next(sync_session())
    try:
        visitor = session.get(Visitor, visitor_id)
        assert visitor is not None
        return visitor.name, visitor.email, visitor.phone
    finally:
        session.close()


def page_fields(conversation_id: uuid.UUID) -> tuple[str | None, str | None, str | None]:
    session = next(sync_session())
    try:
        convo = session.get(Conversation, conversation_id)
        assert convo is not None
        return convo.page_url, convo.page_title, convo.referrer
    finally:
        session.close()


def bootstrap_payload(
    site_key: str = DEMO_SITE_KEY,
    public_key: str = DEMO_PUBLIC_KEY,
    resume_token: str | None = None,
) -> dict[str, str]:
    payload = {"site_key": site_key, "public_key": public_key}
    if resume_token is not None:
        payload["resume_token"] = resume_token
    return payload


def post_bootstrap(
    client: TestClient,
    payload: dict[str, Any] | None = None,
    *,
    origin: str | None = HOST_ORIGIN,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    headers: dict[str, str] = {"Content-Type": "text/plain;charset=UTF-8"}
    if origin is not None:
        headers["Origin"] = origin
    if extra_headers:
        headers.update(extra_headers)
    body = json.dumps(payload if payload is not None else bootstrap_payload())
    return client.post("/api/public/widget-bootstrap", content=body, headers=headers)


def decode_widget_token(token: str) -> dict[str, Any]:
    import jwt

    return jwt.decode(token, "w" * 64, algorithms=["HS256"])


def login_staff(client: TestClient, email: str = ALEX_EMAIL, password: str = ALEX_PASSWORD) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def collect_until(
    websocket: Any,
    done: Callable[[list[dict[str, Any]]], bool],
    limit: int = 40,
) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    while not done(frames) and len(frames) < limit:
        try:
            frames.append(websocket.receive_json())
        except WebSocketDisconnect as exc:
            raise AssertionError(
                f"socket closed code={exc.code} reason={exc.reason!r} after {frames!r}"
            ) from exc
    return frames


def frames_of_type(frames: list[dict[str, Any]], frame_type: str) -> list[dict[str, Any]]:
    return [frame for frame in frames if frame.get("type") == frame_type]


def auth_visitor(websocket: Any, bootstrap_token: str, parent_origin: str = HOST_ORIGIN) -> None:
    websocket.send_json(
        {
            "v": 1,
            "type": "auth",
            "bootstrap_token": bootstrap_token,
            "parent_origin": parent_origin,
        }
    )


def auth_agent(websocket: Any, access_token: str) -> None:
    websocket.send_json({"v": 1, "type": "auth", "access_token": access_token})
