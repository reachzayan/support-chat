import uuid
from datetime import UTC, datetime
from ipaddress import IPv4Address

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.site import Site
from app.models.visitor import Visitor
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    BG_PUBLIC_KEY,
    BG_SITE_KEY,
    DOT_QUESTION,
    EASY_PUBLIC_KEY,
    EASY_SITE_KEY,
    HOST_ORIGIN,
    PRECHAT_SUBMISSION_ID,
    WIDGET_ORIGIN,
    auth_visitor,
    bootstrap_payload,
    collect_until,
    conversation_state,
    insert_site,
    insert_staff,
    login_staff,
    message_count,
    post_bootstrap,
    sync_session,
)

BLOCKED_IP = "203.0.113.40"
OTHER_IP = "198.51.100.20"
ADA_EMAIL = "ada@example.com"


def _session() -> Session:
    return next(sync_session())


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _staff(client: TestClient) -> str:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    return login_staff(client)


def test_block_requires_staff_and_an_identifier(client: TestClient) -> None:
    easy_id = insert_site(EASY_SITE_KEY, "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    denied = client.post(
        "/api/visitor-blocks",
        json={"site_id": str(easy_id), "ip": BLOCKED_IP},
    )
    assert denied.status_code == 401

    token = _staff(client)
    empty = client.post(
        "/api/visitor-blocks",
        headers=_auth(token),
        json={"site_id": str(easy_id)},
    )
    assert empty.status_code == 422
    assert empty.json() == {"detail": "Select at least one identifier."}


def test_ip_block_is_site_scoped_and_unblocks(client: TestClient) -> None:
    easy_id = insert_site(EASY_SITE_KEY, "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_site(BG_SITE_KEY, "Sample Services", BG_PUBLIC_KEY, [HOST_ORIGIN])
    token = _staff(client)
    created = client.post(
        "/api/visitor-blocks",
        headers=_auth(token),
        json={"site_id": str(easy_id), "ip": BLOCKED_IP},
    )
    assert created.status_code == 201
    block_id = created.json()["id"]
    assert created.json()["ip"] == BLOCKED_IP
    assert created.json()["site_name"] == "SampleSite"

    listed = client.get("/api/visitor-blocks", headers=_auth(token))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == block_id
    assert listed.json()["items"][0]["created_by_name"] == ALEX_NAME

    client._transport.client = (BLOCKED_IP, 50000)
    easy_blocked = post_bootstrap(client, bootstrap_payload(EASY_SITE_KEY, EASY_PUBLIC_KEY))
    background = post_bootstrap(client, bootstrap_payload(BG_SITE_KEY, BG_PUBLIC_KEY))
    assert easy_blocked.status_code == 403
    assert easy_blocked.json() == {"detail": "Forbidden"}
    assert background.status_code == 200

    removed = client.delete(f"/api/visitor-blocks/{block_id}", headers=_auth(token))
    assert removed.status_code == 204
    restored = post_bootstrap(client, bootstrap_payload(EASY_SITE_KEY, EASY_PUBLIC_KEY))
    assert restored.status_code == 200


def test_email_block_rejects_prechat_on_that_site(client: TestClient) -> None:
    easy_id = insert_site(EASY_SITE_KEY, "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    token = _staff(client)
    blocked = client.post(
        "/api/visitor-blocks",
        headers=_auth(token),
        json={"site_id": str(easy_id), "email": "Ada@example.com"},
    )
    assert blocked.status_code == 201
    assert blocked.json()["email"] == ADA_EMAIL

    client._transport.client = (OTHER_IP, 50000)
    boot = post_bootstrap(client, bootstrap_payload(EASY_SITE_KEY, EASY_PUBLIC_KEY))
    assert boot.status_code == 200
    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, boot.json()["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": PRECHAT_SUBMISSION_ID,
                "name": "Ada Lopez",
                "email": "Ada@example.com",
                "phone": "",
                "inquiry_type": "results",
                "message": DOT_QUESTION,
            }
        )
        frames = collect_until(
            visitor, lambda items: any(item.get("type") == "error" for item in items)
        )
        assert frames[-1]["type"] == "error"
        assert frames[-1]["code"] == "forbidden"


def test_block_closes_open_conversation(client: TestClient) -> None:
    session = _session()
    try:
        site = Site(
            key=EASY_SITE_KEY,
            name="SampleSite",
            public_key=EASY_PUBLIC_KEY,
            allowed_origins=[HOST_ORIGIN],
            greeting="Talk to a specialist about screening.",
            privacy_url="http://localhost:3000/privacy",
        )
        session.add(site)
        session.flush()
        visitor = Visitor(
            site_id=site.id,
            resume_token_hash=uuid.uuid4().hex,
            name="Ada Lopez",
            email="Ada@example.com",
            ip=IPv4Address(BLOCKED_IP),
        )
        session.add(visitor)
        session.flush()
        now = datetime(2026, 9, 9, 15, 0, tzinfo=UTC)
        conversation = Conversation(
            site_id=site.id,
            visitor_id=visitor.id,
            state="queued",
            last_message_at=now,
            created_at=now,
            prechat_submission_id=uuid.uuid4(),
            prechat_payload_hash="ada-form",
        )
        session.add(conversation)
        session.commit()
        conversation_id = conversation.id
        site_id = site.id
    finally:
        session.close()

    token = _staff(client)
    created = client.post(
        "/api/visitor-blocks",
        headers=_auth(token),
        json={"site_id": str(site_id), "email": ADA_EMAIL, "ip": BLOCKED_IP},
    )
    assert created.status_code == 201
    assert conversation_state(conversation_id) == "closed"
    assert message_count(conversation_id, role="system", body="This chat was closed.") == 0
    assert message_count(conversation_id) == 0

    detail = client.get(f"/api/conversations/{conversation_id}", headers=_auth(token))
    assert detail.status_code == 200
    assert detail.json()["blocked"] is True
    assert detail.json()["block_id"] == created.json()["id"]
    assert [row["body"] for row in detail.json()["messages"]] == []

    listed = client.get("/api/conversations/submissions", headers=_auth(token))
    assert listed.status_code == 200
    ada = listed.json()["items"][0]
    assert ada["visitor"]["email"] == "Ada@example.com"
    assert ada["blocked"] is True
    assert ada["block_id"] == created.json()["id"]


def test_repeat_block_keeps_a_single_row(client: TestClient) -> None:
    easy_id = insert_site(EASY_SITE_KEY, "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    token = _staff(client)
    payload = {"site_id": str(easy_id), "email": ADA_EMAIL}
    first = client.post("/api/visitor-blocks", headers=_auth(token), json=payload)
    second = client.post("/api/visitor-blocks", headers=_auth(token), json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    listed = client.get("/api/visitor-blocks", headers=_auth(token))
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    assert listed.json()["items"][0]["id"] == first.json()["id"]
    assert listed.json()["items"][0]["email"] == ADA_EMAIL


def test_submissions_mark_blocked_visitor(client: TestClient) -> None:
    session = _session()
    try:
        site = Site(
            key=EASY_SITE_KEY,
            name="SampleSite",
            public_key=EASY_PUBLIC_KEY,
            allowed_origins=[HOST_ORIGIN],
            greeting="Talk to a specialist about screening.",
            privacy_url="http://localhost:3000/privacy",
        )
        session.add(site)
        session.flush()
        ada = Visitor(
            site_id=site.id,
            resume_token_hash=uuid.uuid4().hex,
            name="Ada Lopez",
            email=ADA_EMAIL,
        )
        casey = Visitor(
            site_id=site.id,
            resume_token_hash=uuid.uuid4().hex,
            name="Casey Ortiz",
            email="casey@example.com",
        )
        session.add_all([ada, casey])
        session.flush()
        now = datetime(2026, 9, 9, 15, 0, tzinfo=UTC)
        session.add(
            Conversation(
                site_id=site.id,
                visitor_id=ada.id,
                state="queued",
                last_message_at=now,
                created_at=now,
                prechat_submission_id=uuid.uuid4(),
                prechat_payload_hash="ada-form",
            )
        )
        session.add(
            Conversation(
                site_id=site.id,
                visitor_id=casey.id,
                state="queued",
                last_message_at=now,
                created_at=now,
                prechat_submission_id=uuid.uuid4(),
                prechat_payload_hash="casey-form",
            )
        )
        session.commit()
        site_id = site.id
    finally:
        session.close()

    token = _staff(client)
    created = client.post(
        "/api/visitor-blocks",
        headers=_auth(token),
        json={"site_id": str(site_id), "email": ADA_EMAIL},
    )
    assert created.status_code == 201
    listed = client.get("/api/conversations/submissions", headers=_auth(token))
    assert listed.status_code == 200
    by_name = {item["visitor"]["name"]: item for item in listed.json()["items"]}
    assert by_name["Ada Lopez"]["blocked"] is True
    assert by_name["Ada Lopez"]["block_id"] == created.json()["id"]
    assert by_name["Casey Ortiz"]["blocked"] is False
    assert by_name["Casey Ortiz"]["block_id"] is None
