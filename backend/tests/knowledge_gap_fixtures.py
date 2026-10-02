"""Seed helpers for the suggested-FAQ API tests (sync session, real Postgres)."""

import hashlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.knowledge_gap import KnowledgeGap, KnowledgeGapHit
from app.models.message import Message
from app.models.visitor import Visitor
from app.services.kb_embedder import configured_embedder_id
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    BG_PUBLIC_KEY,
    EASY_PUBLIC_KEY,
    HOST_ORIGIN,
    insert_site,
    insert_staff,
    login_staff,
    sync_session,
)

ADMIN_EMAIL = "admin@example.local"
ENROLL = "How do I enroll a driver?"
PRICING = "How much does it cost?"
REPORT = "Where is my report?"
ANSWER = "Enroll drivers from the portal under Drivers."
NOW = datetime.now(UTC)

# How long before NOW a chat asked: whole days, or an exact timedelta for the spike rule.
Age = int | timedelta


def age_of(age: Age) -> timedelta:
    return timedelta(days=age) if isinstance(age, int) else age


@contextmanager
def db() -> Iterator[Session]:
    session = next(sync_session())
    try:
        yield session
        session.commit()
    finally:
        session.close()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_conversation(session: Session, site_id: uuid.UUID) -> uuid.UUID:
    visitor = Visitor(
        site_id=site_id, resume_token_hash=uuid.uuid4().hex, name="Ada Lopez", email="a@x.test"
    )
    session.add(visitor)
    session.flush()
    conversation = Conversation(site_id=site_id, visitor_id=visitor.id, state="bot")
    session.add(conversation)
    session.flush()
    return conversation.id


def seed_hit(
    session: Session,
    site_id: uuid.UUID,
    gap_id: uuid.UUID,
    question: str,
    age: Age,
    conversation_id: uuid.UUID | None = None,
) -> uuid.UUID:
    conversation_id = conversation_id or seed_conversation(session, site_id)
    session.add(
        Message(
            conversation_id=conversation_id,
            site_id=site_id,
            role="visitor",
            client_message_id=uuid.uuid4(),
            body=question,
        )
    )
    reply = Message(
        conversation_id=conversation_id,
        site_id=site_id,
        role="bot",
        body="Could you rephrase that?",
        system_reason="clarify",
    )
    session.add(reply)
    session.flush()
    session.add(
        KnowledgeGapHit(
            site_id=site_id,
            gap_id=gap_id,
            conversation_id=conversation_id,
            message_id=reply.id,
            question=question,
            reason="no_evidence",
            created_at=NOW - age_of(age),
        )
    )
    session.flush()
    return conversation_id


def seed_gap(
    site_id: uuid.UUID,
    question: str,
    asks: list[tuple[str, Age]],
    status: str = "open",
    **gap_fields,
) -> uuid.UUID:
    """One chat per ask, each a (question text, age) pair."""
    with db() as session:
        gap = KnowledgeGap(site_id=site_id, question=question, status=status, **gap_fields)
        session.add(gap)
        session.flush()
        for text, age in asks:
            seed_hit(session, site_id, gap.id, text, age)
        return gap.id


def chats(question: str, ages: list[Age]) -> list[tuple[str, Age]]:
    return [(question, age) for age in ages]


def agent_message(
    session: Session, site_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID, body: str
) -> None:
    session.add(
        Message(
            conversation_id=conversation_id,
            site_id=site_id,
            role="agent",
            author_user_id=user_id,
            client_message_id=uuid.uuid4(),
            body=body,
        )
    )
    session.flush()


def world(client: TestClient) -> tuple[uuid.UUID, uuid.UUID, str, str]:
    easy_id = insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    insert_staff(ADMIN_EMAIL, "Admin", ALEX_PASSWORD, is_admin=True)
    background_id = insert_site(
        "backgroundchecks", "Sample Services", BG_PUBLIC_KEY, [HOST_ORIGIN]
    )
    return (
        easy_id,
        background_id,
        login_staff(client),
        login_staff(client, ADMIN_EMAIL, ALEX_PASSWORD),
    )


def seed_chunk(
    session: Session, site_id: uuid.UUID, title: str, body: str, embedding: list[float]
) -> uuid.UUID:
    """A live, enabled knowledge chunk with a known vector (the sync twin of insert_chunk)."""
    path = uuid.uuid4().hex
    url = f"https://legacy.test/{path}"
    digest = hashlib.sha256(body.encode()).hexdigest()
    source = KbSource(
        site_id=site_id,
        start_url=url,
        mode="list",
        seed_urls=[url],
        status="ready",
        page_count=1,
        embedder_id=configured_embedder_id(),
        source_kind="legacy_faq",
        enabled=True,
    )
    session.add(source)
    session.flush()
    page = KbPage(
        source_id=source.id,
        site_id=site_id,
        url=url,
        title=title,
        content_text=body,
        content_sha256=digest,
        http_status=200,
        enabled=True,
    )
    session.add(page)
    session.flush()
    snapshot = KbSnapshot(
        site_id=site_id, source_id=source.id, state="live", content_hash=digest, token_estimate=0
    )
    session.add(snapshot)
    session.flush()
    chunk = KbChunk(
        page_id=page.id,
        site_id=site_id,
        snapshot_id=snapshot.id,
        ordinal=0,
        kind="prose",
        heading=title,
        canonical_question=title,
        answer_verbatim=body,
        aliases=[],
        body=body,
        embedding=embedding,
        enabled=True,
    )
    session.add(chunk)
    session.flush()
    return chunk.id
