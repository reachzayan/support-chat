import csv
import uuid
from datetime import UTC, datetime
from io import StringIO

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.site import Site
from app.models.visitor import Visitor
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    HOST_ORIGIN,
    insert_staff,
    login_staff,
    sync_session,
)

EASY_KEY = "samplesite"
BG_KEY = "backgroundchecks"
ADA_NAME = "Ada Lopez"
ADA_EMAIL = "ada@example.com"
BLAIR_NAME = "Blair Diaz"
CASEY_NAME = "Casey Ortiz"


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


def _insert_submitted_chat(
    session: Session,
    site: Site,
    *,
    name: str,
    email: str,
    created_at: datetime,
) -> Conversation:
    visitor = Visitor(
        site_id=site.id,
        resume_token_hash=uuid.uuid4().hex,
        name=name,
        email=email,
    )
    session.add(visitor)
    session.flush()
    conversation = Conversation(
        site_id=site.id,
        visitor_id=visitor.id,
        state="queued",
        last_message_at=created_at,
        created_at=created_at,
        prechat_submission_id=uuid.uuid4(),
        prechat_payload_hash=f"{name}-form",
    )
    session.add(conversation)
    session.flush()
    return conversation


def _seed_export_rows(session: Session) -> uuid.UUID:
    easy = _insert_site(session, EASY_KEY, "SampleSite")
    background = _insert_site(session, BG_KEY, "Sample Services")
    _insert_submitted_chat(
        session,
        easy,
        name=ADA_NAME,
        email=ADA_EMAIL,
        created_at=datetime(2026, 9, 1, 15, 0, tzinfo=UTC),
    )
    _insert_submitted_chat(
        session,
        easy,
        name=BLAIR_NAME,
        email="blair@example.com",
        created_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
    )
    _insert_submitted_chat(
        session,
        background,
        name=CASEY_NAME,
        email="casey@example.com",
        created_at=datetime(2026, 9, 5, 9, 0, tzinfo=UTC),
    )
    session.commit()
    return easy.id


def _csv_rows(text: str) -> list[list[str]]:
    return list(csv.reader(StringIO(text)))


def test_export_keeps_easy_screen_date_window_and_requested_columns(client: TestClient) -> None:
    session = _session()
    try:
        easy_id = _seed_export_rows(session)
    finally:
        session.close()

    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    token = login_staff(client)
    exported = client.post(
        "/api/conversations/submissions/export",
        headers=_auth(token),
        json={
            "columns": ["Name", "Email"],
            "site_id": str(easy_id),
            "date_from": "2026-09-01",
            "date_to": "2026-09-10",
        },
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    rows = _csv_rows(exported.text)
    assert rows == [["Name", "Email"], [ADA_NAME, ADA_EMAIL]]


def test_export_requires_staff_and_rejects_unknown_columns(client: TestClient) -> None:
    denied = client.post(
        "/api/conversations/submissions/export",
        json={"columns": ["Name"]},
    )
    assert denied.status_code == 401

    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    token = login_staff(client)
    unknown = client.post(
        "/api/conversations/submissions/export",
        headers=_auth(token),
        json={"columns": ["Transcript"]},
    )
    assert unknown.status_code == 422
    assert unknown.json() == {"detail": "Unknown column."}
