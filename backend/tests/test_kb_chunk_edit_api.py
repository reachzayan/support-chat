import hashlib
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.site import Site
from app.models.user import User
from app.security.passwords import hash_password
from app.services.kb_embedder import FakeEmbedder, configured_embedder_id
from tests.ws_helpers import login_staff, sync_session

ADMIN_EMAIL = "admin@example.local"
ADMIN_PASSWORD = "secret"
ORIGINAL_BODY = "Most negative results are reported within 24-48 hours."
EDITED_BODY = "FCRA-compliant employment screening packages include county searches."


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _insert_admin() -> None:
    session = next(sync_session())
    try:
        session.add(
            User(
                email=ADMIN_EMAIL,
                display_name="Riley Chen",
                password_hash=hash_password(ADMIN_PASSWORD),
                is_admin=True,
                is_active=True,
            )
        )
        session.commit()
    finally:
        session.close()


def _seed_live_chunk() -> str:
    session = next(sync_session())
    try:
        site = Site(
            key="samplesite",
            name="SampleSite",
            public_key="e" * 64,
            allowed_origins=["https://sample-site.example.com"],
            greeting="Talk to a specialist about screening.",
            privacy_url="https://sample-site.example.com/privacy",
        )
        session.add(site)
        session.flush()
        source = KbSource(
            site_id=site.id,
            start_url="https://sample-site.example.com/faq",
            mode="list",
            seed_urls=["https://sample-site.example.com/faq"],
            status="ready",
            page_count=1,
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add(source)
        session.flush()
        page = KbPage(
            source_id=source.id,
            site_id=site.id,
            url="https://sample-site.example.com/faq",
            title="Turnaround",
            content_text=ORIGINAL_BODY,
            content_sha256=hashlib.sha256(ORIGINAL_BODY.encode()).hexdigest(),
            http_status=200,
            enabled=True,
        )
        session.add(page)
        session.flush()
        snapshot = KbSnapshot(
            site_id=site.id,
            source_id=source.id,
            state="live",
            content_hash=hashlib.sha256(ORIGINAL_BODY.encode()).hexdigest(),
            token_estimate=0,
        )
        session.add(snapshot)
        session.flush()
        chunk = KbChunk(
            page_id=page.id,
            site_id=site.id,
            snapshot_id=snapshot.id,
            ordinal=0,
            kind="section",
            heading="Turnaround",
            body=ORIGINAL_BODY,
            answer_verbatim=ORIGINAL_BODY,
            enabled=True,
        )
        session.add(chunk)
        session.commit()
        return str(chunk.id)
    finally:
        session.close()


def test_admin_can_edit_a_retrieved_answer_and_replays_are_stable(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr("app.services.kb_source_admin.default_embedder", lambda: FakeEmbedder())
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    chunk_id = _seed_live_chunk()
    edit_id = str(uuid4())
    first = client.patch(
        f"/api/kb-chunks/{chunk_id}",
        headers=_auth(admin),
        json={"body": EDITED_BODY, "edit_id": edit_id},
    )
    assert first.status_code == 200
    assert first.json()["body"] == EDITED_BODY
    assert first.json()["last_body_edit_id"] == edit_id
    replay = client.patch(
        f"/api/kb-chunks/{chunk_id}",
        headers=_auth(admin),
        json={"body": EDITED_BODY, "edit_id": edit_id},
    )
    assert replay.status_code == 200
    assert replay.json()["body"] == EDITED_BODY
    conflict = client.patch(
        f"/api/kb-chunks/{chunk_id}",
        headers=_auth(admin),
        json={"body": "Something else a specialist never saved.", "edit_id": edit_id},
    )
    assert conflict.status_code == 409
    stored = client.patch(
        f"/api/kb-chunks/{chunk_id}",
        headers=_auth(admin),
        json={"enabled": True},
    )
    assert stored.json()["body"] == EDITED_BODY
    assert UUID(stored.json()["id"]) == UUID(chunk_id)
