import hashlib
from uuid import UUID

from fastapi.testclient import TestClient

from app.db import session_maker
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.site import Site
from app.models.user import User
from app.security.passwords import hash_password
from app.services.kb_embedder import configured_embedder_id
from app.services.kb_ingest import ingest_source
from app.services.kb_search import KbSearch
from app.services.kb_source_admin import KbSourceService
from tests.bot_fixtures import insert_site
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    insert_staff,
    login_staff,
    sync_session,
)

ADMIN_EMAIL = "admin@example.local"
ADMIN_PASSWORD = "secret"
FAQ_URL = "https://sample-site.example.com/faq"
TIMING_TITLE = "Turnaround"
TIMING_BODY = "Most negative results are reported within 24-48 hours."
TIMING_HTML = (
    "<html><body><nav>Careers</nav><main><h1>Turnaround</h1>"
    "<p>Most negative results are reported within 24-48 hours.</p></main></body></html>"
)
DOT_HTML = (
    "<html><body><main><h1>DOT</h1>"
    "<p>DOT-regulated testing follows federal rules for prohibited substances.</p>"
    "</main></body></html>"
)


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


def _create_easy_site(client: TestClient, token: str) -> str:
    site = client.post(
        "/api/sites",
        headers=_auth(token),
        json={
            "key": "samplesite",
            "name": "SampleSite",
            "greeting": "Talk to a specialist about screening.",
            "privacy_url": "https://sample-site.example.com/privacy",
            "origins": ["https://sample-site.example.com"],
        },
    )
    return site.json()["id"]


def test_non_admin_cannot_create_source(client: TestClient) -> None:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    alex = login_staff(client)
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)
    denied = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(alex),
        json={
            "mode": "list",
            "start_url": "https://sample-site.example.com/faq",
            "seed_urls": ["https://sample-site.example.com/faq"],
        },
    )
    assert denied.status_code == 403


def test_background_checks_url_on_samplesite_is_422(client: TestClient) -> None:
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)
    rejected = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={
            "mode": "list",
            "start_url": "https://sample-site.example.com/faq",
            "seed_urls": ["https://sample-services.example.com/fcra"],
        },
    )
    assert rejected.status_code == 422


def test_admin_create_source_is_queued(client: TestClient) -> None:
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)
    created = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={
            "mode": "list",
            "start_url": "https://sample-site.example.com/faq",
            "seed_urls": ["https://sample-site.example.com/faq"],
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "queued"
    assert created.json()["page_count"] == 0
    source_id = created.json()["id"]
    deleted = client.delete(f"/api/kb-sources/{source_id}", headers=_auth(admin))
    assert deleted.status_code == 204


def test_admin_create_source_stays_queued_when_wakeup_fails(
    client: TestClient, monkeypatch
) -> None:
    class _BoomRedis:
        async def rpush(self, *_args, **_kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr("app.services.kb_ingest.get_redis", lambda: _BoomRedis())
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)
    created = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={
            "mode": "list",
            "start_url": "https://sample-site.example.com/dot",
            "seed_urls": ["https://sample-site.example.com/dot"],
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "queued"
    assert created.json()["page_count"] == 0


def test_get_page_returns_indexed_copy_and_chunks(client: TestClient) -> None:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    alex = login_staff(client)
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = UUID(_create_easy_site(client, admin))
    session = next(sync_session())
    try:
        site = session.get(Site, site_id)
        assert site is not None
        source = KbSource(
            site_id=site.id,
            start_url=FAQ_URL,
            mode="list",
            seed_urls=[FAQ_URL],
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
            url=FAQ_URL,
            title=TIMING_TITLE,
            content_text=TIMING_BODY,
            content_sha256=hashlib.sha256(TIMING_BODY.encode()).hexdigest(),
            http_status=200,
            enabled=True,
        )
        session.add(page)
        session.flush()
        snapshot = KbSnapshot(
            site_id=site.id,
            source_id=source.id,
            state="live",
            content_hash=hashlib.sha256(TIMING_BODY.encode()).hexdigest(),
            token_estimate=0,
        )
        session.add(snapshot)
        session.flush()
        session.add(
            KbChunk(
                page_id=page.id,
                site_id=site.id,
                snapshot_id=snapshot.id,
                ordinal=0,
                heading=TIMING_TITLE,
                body=TIMING_BODY,
                answer_verbatim=TIMING_BODY,
                enabled=True,
            )
        )
        session.commit()
        page_id = str(page.id)
    finally:
        session.close()
    detail = client.get(f"/api/kb-pages/{page_id}", headers=_auth(alex))
    payload = detail.json()
    assert payload["url"] == FAQ_URL
    assert payload["title"] == TIMING_TITLE
    assert payload["content_text"] == TIMING_BODY
    assert payload["skip_reason"] is None
    assert payload["chunks"] == [
        {"ordinal": 0, "heading": TIMING_TITLE, "body": TIMING_BODY, "enabled": True}
    ]


async def test_list_ingest_stores_two_pages_then_delete_empties_search(migrated_db) -> None:
    pages = {
        "https://sample-site.example.com/faq": TIMING_HTML,
        "https://sample-site.example.com/dot": DOT_HTML,
    }

    def fake_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
        return pages[url]

    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        site.allowed_origins = ["https://sample-site.example.com"]
        source = KbSource(
            site_id=site.id,
            start_url="https://sample-site.example.com/faq",
            mode="list",
            seed_urls=[
                "https://sample-site.example.com/faq",
                "https://sample-site.example.com/dot",
            ],
            status="queued",
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add(source)
        await session.commit()
        source_id = source.id
        site_id = site.id
        await ingest_source(session, source_id, fetch=fake_fetch)

    async with session_maker()() as session:
        source = await session.get(KbSource, source_id)
        assert source is not None
        assert source.page_count == 2
        assert source.status == "ready"
        listed = await KbSourceService(session).list_pages(source_id)
        assert len(listed) == 2
        # Site-owned ingestion is live and searchable as soon as validation passes.
        hits = await KbSearch(session).search(site_id, "how fast are results")
        assert hits
        await KbSourceService(session).delete_source(source_id)
        empty = await KbSearch(session).search(site_id, "how fast are results")
        assert empty == []


def test_fragment_and_root_url_collapse_to_one_source(client: TestClient) -> None:
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)
    first = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={
            "mode": "list",
            "start_url": "https://sample-site.example.com/",
            "seed_urls": ["https://sample-site.example.com/"],
        },
    )
    second = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={
            "mode": "list",
            "start_url": "https://sample-site.example.com/#faq",
            "seed_urls": ["https://sample-site.example.com/#faq"],
        },
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    listed = client.get(f"/api/sites/{site_id}/kb-sources", headers=_auth(admin))
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == first.json()["id"]
    assert items[0]["start_url"] == "https://sample-site.example.com/"
    assert items[0]["status"] == "queued"
    assert items[0]["page_count"] == 0
    assert items[0]["stage"] == "idle"
    assert items[0]["pages_discovered"] == 0


async def test_snapshots_diff_and_rollback(migrated_db) -> None:
    from fastapi.testclient import TestClient

    from app.db import reset_engine
    from app.main import create_app
    from app.services.kb_snapshot import begin_snapshot, fail, promote

    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        site.allowed_origins = ["https://sample-site.example.com"]
        source = KbSource(
            site_id=site.id,
            start_url=FAQ_URL,
            mode="list",
            seed_urls=[FAQ_URL],
            status="ready",
            page_count=1,
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add(source)
        await session.flush()
        first = await begin_snapshot(session, source.id)
        second = await begin_snapshot(session, source.id)
        await promote(session, first)
        await fail(session, second, "validation")
        await session.commit()
        source_id = source.id
        first_id = first

    # Roll the second snapshot into a comparable pair via the service after a live exists.
    async with session_maker()() as session:
        third = await begin_snapshot(session, source_id)
        await promote(session, third)
        await session.commit()
        third_id = third

    from tests.ws_helpers import login_staff as login

    _insert_admin()
    reset_engine()
    with TestClient(create_app()) as client:
        admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        snapshots = client.get(f"/api/kb-sources/{source_id}/snapshots", headers=_auth(admin))
        states = {row["id"]: row["state"] for row in snapshots.json()["items"]}
        assert states[str(first_id)] == "superseded"
        assert states[str(third_id)] == "live"
        diff = client.get(
            f"/api/kb-sources/{source_id}/diff",
            params={"from": str(first_id), "to": str(third_id)},
            headers=_auth(admin),
        )
        payload = diff.json()
        assert set(payload.keys()) == {"added", "changed", "removed"}
        rolled = client.post(f"/api/kb-sources/{source_id}/rollback", headers=_auth(admin))
        assert rolled.json()["id"] == str(first_id)
        assert rolled.json()["state"] == "live"
