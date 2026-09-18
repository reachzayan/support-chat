import uuid
from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Address

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.canned_reply import CannedReply
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.site import Site
from app.models.visitor import Visitor
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    DOT_QUESTION,
    EASY_PUBLIC_KEY,
    HOST_ORIGIN,
    WIDGET_ORIGIN,
    auth_visitor,
    bootstrap_payload,
    collect_until,
    decode_widget_token,
    insert_staff,
    login_staff,
    message_count,
    post_bootstrap,
    sync_session,
)

EASY_NAME = "SampleSite"
EASY_KEY = "samplesite"
ADA_NAME = "Ada Lopez"
ADA_EMAIL = "ada@example.com"
ADA_IP = "203.0.113.40"
ADA_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
PAGE_TITLE = "DOT screening"
PAGE_URL = "https://sample-site.example.com/dot"
REFERRER = "https://sample-site.example.com/"
UPDATED_TITLE = "Portal login"
UPDATED_URL = "http://localhost:3000/portal"
SECOND_VISITOR_LINE = "Please confirm the portal login."
HOURS_BODY = "Most negative results are reported within 24-48 hours."
PREVIEW_SOURCE = (
    "Negative screening results for this DOT file usually post to the employer portal overnight."
)
PREVIEW_80 = "Negative screening results for this DOT file usually post to the employer portal"


def _session() -> Session:
    return next(sync_session())


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _insert_site(session: Session, key: str, name: str) -> Site:
    site = Site(
        key=key,
        name=name,
        public_key=uuid.uuid4().hex + uuid.uuid4().hex,
        allowed_origins=[HOST_ORIGIN],
        greeting="Talk to a specialist about screening.",
        privacy_url="http://localhost:3000/privacy",
    )
    session.add(site)
    session.flush()
    return site


def _insert_visitor(
    session: Session,
    site: Site,
    *,
    name: str | None,
    email: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> Visitor:
    visitor = Visitor(
        site_id=site.id,
        resume_token_hash=uuid.uuid4().hex,
        name=name,
        email=email,
        ip=IPv4Address(ip) if ip else None,
        user_agent=user_agent,
    )
    session.add(visitor)
    session.flush()
    return visitor


def _insert_conversation(
    session: Session,
    site: Site,
    visitor: Visitor,
    state: str,
    *,
    last_message_at: datetime,
    inquiry_type: str | None = None,
    intent: str | None = None,
    page_title: str | None = None,
    page_url: str | None = None,
    referrer: str | None = None,
    assigned_agent_id: uuid.UUID | None = None,
    closed_at: datetime | None = None,
) -> Conversation:
    conversation = Conversation(
        site_id=site.id,
        visitor_id=visitor.id,
        state=state,
        inquiry_type=inquiry_type,
        intent=intent,
        page_title=page_title,
        page_url=page_url,
        referrer=referrer,
        assigned_agent_id=assigned_agent_id,
        last_message_at=last_message_at,
        closed_at=closed_at,
    )
    session.add(conversation)
    session.flush()
    return conversation


def _insert_visitor_message(
    session: Session, conversation_id: uuid.UUID, body: str, created_at: datetime
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        client_message_id=uuid.uuid4(),
        role="visitor",
        body=body,
        created_at=created_at,
    )
    session.add(message)
    session.flush()
    return message


def _seed_staff(client: TestClient) -> str:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    return login_staff(client)


def test_queued_filter_returns_only_queued_and_public_cannot_read_detail(
    client: TestClient,
) -> None:
    session = _session()
    try:
        site = _insert_site(session, EASY_KEY, EASY_NAME)
        queued_visitor = _insert_visitor(session, site, name=ADA_NAME, email=ADA_EMAIL, ip=ADA_IP)
        closed_visitor = _insert_visitor(
            session, site, name="Closed Candidate", email="closed@example.com", ip="203.0.113.41"
        )
        now = datetime(2026, 9, 9, 15, 0, tzinfo=UTC)
        queued = _insert_conversation(
            session,
            site,
            queued_visitor,
            "queued",
            last_message_at=now,
            inquiry_type="results",
        )
        closed = _insert_conversation(
            session,
            site,
            closed_visitor,
            "closed",
            last_message_at=now - timedelta(hours=2),
            closed_at=now - timedelta(hours=1),
        )
        _insert_visitor_message(session, queued.id, DOT_QUESTION, now)
        _insert_visitor_message(session, closed.id, PREVIEW_SOURCE, now - timedelta(hours=2))
        session.commit()
        queued_id = str(queued.id)
        closed_id = str(closed.id)
    finally:
        session.close()

    token = _seed_staff(client)
    listed = client.get("/api/conversations", params={"state": "queued"}, headers=_auth(token))
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()["items"]]
    assert ids == [queued_id]
    assert closed_id not in ids
    assert listed.json()["items"][0]["visitor_display"] == ADA_NAME
    assert listed.json()["items"][0]["site_name"] == EASY_NAME
    assert listed.json()["items"][0]["state"] == "queued"
    assert listed.json()["items"][0]["preview"] == DOT_QUESTION

    unauthenticated = client.get(f"/api/conversations/{queued_id}")
    assert unauthenticated.status_code == 401
    public = client.get(f"/api/public/conversations/{queued_id}")
    assert public.status_code == 404
    listed_anon = client.get("/api/conversations", params={"state": "queued"})
    assert listed_anon.status_code == 401


def test_detail_returns_ada_lopez_facts_and_hello_does_not_add_a_row(
    client: TestClient,
) -> None:
    session = _session()
    try:
        site = Site(
            key=EASY_KEY,
            name=EASY_NAME,
            public_key=EASY_PUBLIC_KEY,
            allowed_origins=[HOST_ORIGIN],
            greeting="Talk to a specialist about screening.",
            privacy_url="http://localhost:3000/privacy",
        )
        session.add(site)
        session.commit()
    finally:
        session.close()

    token = _seed_staff(client)
    boot = post_bootstrap(client, bootstrap_payload(EASY_KEY, EASY_PUBLIC_KEY))
    assert boot.status_code == 200
    claims = decode_widget_token(boot.json()["bootstrap_token"])
    conversation_id = uuid.UUID(claims["conversation_id"])
    visitor_id = uuid.UUID(claims["visitor_id"])

    session = _session()
    try:
        visitor = session.get(Visitor, visitor_id)
        assert visitor is not None
        visitor.name = ADA_NAME
        visitor.email = ADA_EMAIL
        visitor.phone = None
        visitor.ip = IPv4Address(ADA_IP)
        visitor.user_agent = ADA_UA
        visitor.location = "New York, New York, United States"
        conversation = session.get(Conversation, conversation_id)
        assert conversation is not None
        conversation.state = "queued"
        conversation.inquiry_type = "results"
        conversation.intent = "turnaround"
        conversation.page_title = PAGE_TITLE
        conversation.page_url = PAGE_URL
        conversation.referrer = REFERRER
        now = datetime(2026, 9, 9, 16, 0, tzinfo=UTC)
        first = _insert_visitor_message(session, conversation.id, DOT_QUESTION, now)
        second = _insert_visitor_message(
            session, conversation.id, SECOND_VISITOR_LINE, now + timedelta(minutes=1)
        )
        conversation.last_message_at = now + timedelta(minutes=1)
        session.commit()
        first_id = first.id
        second_id = second.id
    finally:
        session.close()

    detail = client.get(f"/api/conversations/{conversation_id}", headers=_auth(token))
    assert detail.status_code == 200
    body = detail.json()
    assert body["visitor"]["name"] == ADA_NAME
    assert body["visitor"]["email"] == ADA_EMAIL
    assert body["visitor"]["phone"] is None
    assert body["visitor"]["ip"] == ADA_IP
    assert body["visitor"]["user_agent"] == ADA_UA
    assert body["visitor"]["location"] == "New York, New York, United States"
    assert body["site_name"] == EASY_NAME
    assert body["page"]["title"] == PAGE_TITLE
    assert body["page"]["url"] == PAGE_URL
    assert body["page"]["referrer"] == REFERRER
    assert body["inquiry_type"] == "results"
    assert body["intent"] == "turnaround"
    assert body["assigned_agent"] is None
    messages = body["messages"]
    assert [row["id"] for row in messages] == [first_id, second_id]
    assert [row["body"] for row in messages] == [DOT_QUESTION, SECOND_VISITOR_LINE]
    assert [row["role"] for row in messages] == ["visitor", "visitor"]
    assert messages[0]["author_user"] is None
    assert messages[0]["source_article_ids"] is None

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor_ws:
        auth_visitor(visitor_ws, boot.json()["bootstrap_token"])
        collect_until(
            visitor_ws, lambda frames: any(frame.get("type") == "state" for frame in frames)
        )
        visitor_ws.send_json(
            {
                "v": 1,
                "type": "hello",
                "page_url": UPDATED_URL,
                "page_title": UPDATED_TITLE,
                "referrer": "",
            }
        )
        collect_until(
            visitor_ws, lambda frames: any(frame.get("type") == "state" for frame in frames)
        )

    refreshed = client.get(f"/api/conversations/{conversation_id}", headers=_auth(token))
    assert refreshed.status_code == 200
    again = refreshed.json()
    assert again["page"]["title"] == UPDATED_TITLE
    assert again["page"]["url"] == UPDATED_URL
    assert [row["id"] for row in again["messages"]] == [first_id, second_id]
    assert message_count(conversation_id) == 2


def test_inbox_counts_are_hand_counted_across_states(client: TestClient) -> None:
    alex_id = insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    session = _session()
    try:
        site = _insert_site(session, EASY_KEY, EASY_NAME)
        now = datetime(2026, 9, 9, 18, 0, tzinfo=UTC)
        queued_one = _insert_visitor(session, site, name="Queued One")
        queued_two = _insert_visitor(session, site, name="Queued Two")
        bot_visitor = _insert_visitor(session, site, name="Bot Visitor")
        live_visitor = _insert_visitor(session, site, name="Live Visitor")
        closed_visitor = _insert_visitor(session, site, name="Closed Visitor")
        prechat_visitor = _insert_visitor(session, site, name="Prechat Visitor")
        _insert_conversation(session, site, queued_one, "queued", last_message_at=now)
        _insert_conversation(
            session, site, queued_two, "queued", last_message_at=now - timedelta(minutes=1)
        )
        _insert_conversation(
            session, site, bot_visitor, "bot", last_message_at=now - timedelta(minutes=2)
        )
        _insert_conversation(
            session,
            site,
            live_visitor,
            "human",
            last_message_at=now - timedelta(minutes=3),
            assigned_agent_id=alex_id,
        )
        _insert_conversation(
            session,
            site,
            closed_visitor,
            "closed",
            last_message_at=now - timedelta(hours=1),
            closed_at=now - timedelta(minutes=30),
        )
        _insert_conversation(
            session, site, prechat_visitor, "prechat", last_message_at=now - timedelta(hours=2)
        )
        session.commit()
    finally:
        session.close()

    token = login_staff(client)
    listed = client.get("/api/conversations", params={"state": "human"}, headers=_auth(token))
    assert listed.status_code == 200
    assert listed.json()["counts"] == {
        "bot": 1,
        "queued": 2,
        "human": 1,
        "closed": 1,
    }
    assert [item["visitor_display"] for item in listed.json()["items"]] == ["Live Visitor"]


def test_preview_is_capped_at_eighty_characters(client: TestClient) -> None:
    session = _session()
    try:
        site = _insert_site(session, EASY_KEY, EASY_NAME)
        visitor = _insert_visitor(session, site, name=ADA_NAME, email=ADA_EMAIL, ip=ADA_IP)
        now = datetime(2026, 9, 9, 17, 0, tzinfo=UTC)
        conversation = _insert_conversation(
            session, site, visitor, "queued", last_message_at=now, inquiry_type="results"
        )
        _insert_visitor_message(session, conversation.id, PREVIEW_SOURCE, now)
        session.commit()
        conversation_id = str(conversation.id)
    finally:
        session.close()

    token = _seed_staff(client)
    listed = client.get("/api/conversations", params={"state": "queued"}, headers=_auth(token))
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["id"] == conversation_id
    assert item["preview"] == PREVIEW_80
    assert len(item["preview"]) == 80


def test_canned_replies_are_site_scoped_and_require_staff(client: TestClient) -> None:
    session = _session()
    try:
        easy = _insert_site(session, EASY_KEY, EASY_NAME)
        other = _insert_site(session, "backgroundchecks", "Sample Services")
        session.add(
            CannedReply(site_id=easy.id, shortcut="hours", body=HOURS_BODY),
        )
        session.add(
            CannedReply(
                site_id=other.id,
                shortcut="hours",
                body="Sample Services hours are posted on the other brand site.",
            ),
        )
        session.commit()
        easy_id = str(easy.id)
        other_id = str(other.id)
    finally:
        session.close()

    assert client.get("/api/canned-replies", params={"site_id": easy_id}).status_code == 401
    token = _seed_staff(client)
    easy_replies = client.get(
        "/api/canned-replies", params={"site_id": easy_id}, headers=_auth(token)
    )
    other_replies = client.get(
        "/api/canned-replies", params={"site_id": other_id}, headers=_auth(token)
    )
    assert easy_replies.status_code == 200
    assert other_replies.status_code == 200
    easy_items = easy_replies.json()["items"]
    other_items = other_replies.json()["items"]
    assert easy_items == [{"shortcut": "hours", "body": HOURS_BODY, "scope": "website"}]
    assert other_items[0]["body"] != HOURS_BODY
    assert other_items[0]["shortcut"] == "hours"
