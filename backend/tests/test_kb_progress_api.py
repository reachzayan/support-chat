from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.site import Site
from app.models.user import User
from app.security.passwords import hash_password
from app.services.kb_embedder import configured_embedder_id
from tests.ws_helpers import login_staff, sync_session

ADMIN_EMAIL = "admin@example.local"
ADMIN_PASSWORD = "secret"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


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


def test_progress_endpoint_lists_recent_finished_jobs(client: TestClient) -> None:
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    session = next(sync_session())
    try:
        site = Site(
            key=f"easy-{uuid4().hex[:8]}",
            name="SampleSite",
            public_key=uuid4().hex + uuid4().hex,
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
            status="running",
            stage="processing",
            pages_discovered=12,
            pages_embedded=7,
            pages_failed=0,
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add(source)
        session.flush()
        snapshot = KbSnapshot(
            site_id=site.id,
            source_id=source.id,
            state="building",
            content_hash="",
            token_estimate=0,
        )
        session.add(snapshot)
        session.flush()
        page = KbPage(
            source_id=source.id,
            site_id=site.id,
            url="https://sample-site.example.com/faq",
            title="Turnaround",
            content_text="Most negative results are reported within 24-48 hours.",
            content_sha256="a" * 64,
            http_status=200,
            enabled=True,
            processing_status="ready",
        )
        session.add(page)
        session.flush()
        started = datetime(2026, 9, 11, 14, 0, tzinfo=UTC)
        session.add(
            KbPageJob(
                source_id=source.id,
                page_id=page.id,
                snapshot_id=snapshot.id,
                stage="persist",
                state="done",
                attempts=1,
                renderer="crawl4ai",
                http_status=200,
                started_at=started,
                finished_at=started + timedelta(milliseconds=812),
            )
        )
        session.commit()
        source_id = str(source.id)
    finally:
        session.close()

    listed = client.get(f"/api/kb-sources/{source_id}/progress", headers=_auth(admin))
    payload = listed.json()
    assert payload["source"]["pages_discovered"] == 12
    assert payload["source"]["pages_embedded"] == 7
    assert payload["recent_events"][0]["page_url"] == "https://sample-site.example.com/faq"
    assert payload["recent_events"][0]["state"] == "done"
    assert payload["recent_events"][0]["duration_ms"] == 812
    assert payload["recent_events"][0]["renderer"] == "crawl4ai"
    assert payload["recent_events"][0]["http_status"] == 200
    assert payload["recent_events"][0]["message"] == "Saved this page."
    assert payload["current_jobs"] == []


def test_progress_endpoint_explains_failed_fetch_in_plain_language(client: TestClient) -> None:
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    session = next(sync_session())
    try:
        site = Site(
            key=f"easy-{uuid4().hex[:8]}",
            name="SampleSite",
            public_key=uuid4().hex + uuid4().hex,
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
            status="failed",
            stage="failed",
            pages_discovered=1,
            pages_embedded=0,
            pages_failed=1,
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add(source)
        session.flush()
        snapshot = KbSnapshot(
            site_id=site.id,
            source_id=source.id,
            state="failed",
            content_hash="",
            token_estimate=0,
        )
        session.add(snapshot)
        session.flush()
        page = KbPage(
            source_id=source.id,
            site_id=site.id,
            url="https://sample-site.example.com/faq",
            title="Turnaround",
            content_text="",
            content_sha256="a" * 64,
            http_status=0,
            enabled=True,
            processing_status="failed",
            failure_reason="browser_crash",
        )
        session.add(page)
        session.flush()
        started = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
        session.add(
            KbPageJob(
                source_id=source.id,
                page_id=page.id,
                snapshot_id=snapshot.id,
                stage="fetch",
                state="dead_letter",
                attempts=5,
                last_error_code="browser_crash",
                renderer="crawl4ai",
                started_at=started,
                finished_at=started + timedelta(milliseconds=1200),
                events=[
                    {
                        "timestamp": "2026-09-16T12:00:00+00:00",
                        "stage": "fetch",
                        "state": "dead_letter",
                        "error_code": "browser_crash",
                        "renderer": "crawl4ai",
                        "http_status": None,
                    }
                ],
            )
        )
        session.commit()
        source_id = str(source.id)
    finally:
        session.close()

    listed = client.get(f"/api/kb-sources/{source_id}/progress", headers=_auth(admin))
    payload = listed.json()
    assert payload["recent_events"][0]["error_code"] == "browser_crash"
    assert payload["recent_events"][0]["message"] == "The browser could not open this page."
