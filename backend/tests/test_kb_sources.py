import hashlib
from uuid import UUID, uuid4

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


def test_admin_create_text_source_is_queued_without_a_public_url(client: TestClient) -> None:
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)

    created = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={
            "kind": "text",
            "title": "Collections policy",
            "body": "Payment plans are reviewed by the collections team.",
        },
    )

    assert created.status_code == 201
    assert created.json()["source_kind"] == "text"
    assert created.json()["display_name"] == "Collections policy"
    assert created.json()["status"] == "queued"
    assert "kb-text://" not in created.text


def test_text_source_rejects_blank_content(client: TestClient) -> None:
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)

    rejected = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={"kind": "text", "title": "Policy", "body": "   "},
    )

    assert rejected.status_code == 422


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
        chunk = KbChunk(
            page_id=page.id,
            site_id=site.id,
            snapshot_id=snapshot.id,
            ordinal=0,
            kind="section",
            heading=TIMING_TITLE,
            body=TIMING_BODY,
            answer_verbatim=TIMING_BODY,
            enabled=True,
        )
        session.add(chunk)
        session.commit()
        page_id = str(page.id)
        chunk_id = str(chunk.id)
    finally:
        session.close()
    pages = client.get(
        f"/api/kb-sources/{source.id}/pages",
        headers=_auth(alex),
    )
    assert pages.json()["items"][0]["chunk_count"] == 1
    detail = client.get(f"/api/kb-pages/{page_id}", headers=_auth(alex))
    payload = detail.json()
    assert payload["url"] == FAQ_URL
    assert payload["title"] == TIMING_TITLE
    assert payload["content_text"] == TIMING_BODY
    assert payload["skip_reason"] is None
    assert payload["chunk_count"] == 1
    assert payload["chunks"] == [
        {
            "id": chunk_id,
            "ordinal": 0,
            "kind": "section",
            "heading": TIMING_TITLE,
            "body": TIMING_BODY,
            "enabled": True,
            "origin_urls": [],
        }
    ]


def test_shared_answers_are_listed_on_a_general_tab(client: TestClient) -> None:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    alex = login_staff(client)
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = UUID(_create_easy_site(client, admin))
    home_url = "https://sample-data.example.com/"
    mail_url = "https://sample-data.example.com/samplemail"
    contact = "Phone: 202-555-0101. Email: inquiries@sample-data.example.com"
    mail_fact = "SampleMail verifies every address before the piece enters the mailstream."
    session = next(sync_session())
    try:
        site = session.get(Site, site_id)
        assert site is not None
        source = KbSource(
            site_id=site.id,
            start_url=home_url,
            mode="list",
            seed_urls=[home_url, mail_url],
            status="ready",
            page_count=2,
            embedder_id=configured_embedder_id(),
            enabled=True,
        )
        session.add(source)
        session.flush()
        home = KbPage(
            source_id=source.id,
            site_id=site.id,
            url=home_url,
            title="Home",
            content_text=contact,
            content_sha256=hashlib.sha256(b"home").hexdigest(),
            http_status=200,
            enabled=True,
        )
        mail = KbPage(
            source_id=source.id,
            site_id=site.id,
            url=mail_url,
            title="SampleMail",
            content_text=mail_fact,
            content_sha256=hashlib.sha256(b"mail").hexdigest(),
            http_status=200,
            enabled=True,
        )
        session.add_all([home, mail])
        session.flush()
        snapshot = KbSnapshot(
            site_id=site.id,
            source_id=source.id,
            state="live",
            content_hash=hashlib.sha256(b"live").hexdigest(),
            token_estimate=0,
        )
        session.add(snapshot)
        session.flush()
        session.add(
            KbChunk(
                page_id=home.id,
                site_id=site.id,
                snapshot_id=snapshot.id,
                ordinal=0,
                kind="section",
                heading="Contact",
                body=contact,
                answer_verbatim=contact,
                origin_urls=[home_url, mail_url],
                enabled=True,
            )
        )
        session.add(
            KbChunk(
                page_id=mail.id,
                site_id=site.id,
                snapshot_id=snapshot.id,
                ordinal=0,
                kind="section",
                heading="SampleMail",
                body=mail_fact,
                answer_verbatim=mail_fact,
                origin_urls=[],
                enabled=True,
            )
        )
        session.commit()
        source_id = str(source.id)
        mail_id = str(mail.id)
    finally:
        session.close()
    listed = client.get(f"/api/kb-sources/{source_id}/pages", headers=_auth(alex)).json()["items"]
    assert [item["title"] for item in listed] == ["General", "Home", "SampleMail"]
    assert listed[0]["tab"] == "general"
    general = client.get(f"/api/kb-pages/{listed[0]['id']}", headers=_auth(alex)).json()
    assert general["title"] == "General"
    assert [chunk["heading"] for chunk in general["chunks"]] == ["Contact"]
    assert general["chunks"][0]["origin_urls"] == [home_url, mail_url]
    mail_detail = client.get(f"/api/kb-pages/{mail_id}", headers=_auth(alex)).json()
    assert [chunk["heading"] for chunk in mail_detail["chunks"]] == ["SampleMail"]


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
    assert items[0]["mode"] == "list"
    assert items[0]["status"] == "queued"
    assert items[0]["page_count"] == 0
    assert items[0]["stage"] == "idle"
    assert items[0]["pages_discovered"] == 0


def test_updating_a_queued_source_does_not_enqueue_a_duplicate_wakeup(
    client: TestClient, monkeypatch
) -> None:
    wakeups: list[UUID] = []

    async def record_wakeup(source_id: UUID) -> None:
        wakeups.append(source_id)

    monkeypatch.setattr("app.services.kb_source_admin.enqueue_wakeup", record_wakeup)
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)
    first = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={"mode": "prefix", "start_url": FAQ_URL, "seed_urls": []},
    )
    updated = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={"mode": "list", "start_url": FAQ_URL, "seed_urls": [FAQ_URL]},
    )

    assert first.status_code == 201
    assert updated.status_code == 201
    assert updated.json()["mode"] == "list"
    assert wakeups == [UUID(first.json()["id"])]


def test_admin_create_respects_explicit_list_mode(client: TestClient) -> None:
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
    assert created.json()["mode"] == "list"


def test_admin_cannot_requeue_a_source_while_it_is_running(client: TestClient) -> None:
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)
    created = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={"mode": "list", "start_url": FAQ_URL, "seed_urls": [FAQ_URL]},
    )
    source_id = UUID(created.json()["id"])
    session = next(sync_session())
    try:
        source = session.get(KbSource, source_id)
        assert source is not None
        source.status = "running"
        session.commit()
    finally:
        session.close()

    duplicate = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={"mode": "list", "start_url": FAQ_URL, "seed_urls": [FAQ_URL]},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "This source is already syncing."


def test_admin_create_rejects_a_url_owned_by_another_source(client: TestClient) -> None:
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)
    first = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={"mode": "list", "start_url": FAQ_URL, "seed_urls": [FAQ_URL]},
    )
    assert first.status_code == 201
    source_id = UUID(first.json()["id"])
    session = next(sync_session())
    try:
        source = session.get(KbSource, source_id)
        assert source is not None
        session.add(
            KbPage(
                source_id=source.id,
                site_id=source.site_id,
                url="https://sample-site.example.com/privacy",
                title="Privacy",
                content_text="Privacy policy copy.",
                content_sha256="b" * 64,
                http_status=200,
                enabled=True,
            )
        )
        session.commit()
    finally:
        session.close()

    second = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={
            "mode": "list",
            "start_url": "https://sample-site.example.com/privacy",
            "seed_urls": ["https://sample-site.example.com/privacy"],
        },
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "This page already belongs to another knowledge source."


def test_admin_can_queue_a_single_failed_page_retry(client: TestClient) -> None:
    _insert_admin()
    admin = login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    site_id = _create_easy_site(client, admin)
    created = client.post(
        f"/api/sites/{site_id}/kb-sources",
        headers=_auth(admin),
        json={"mode": "list", "start_url": FAQ_URL, "seed_urls": [FAQ_URL]},
    )
    source_id = UUID(created.json()["id"])
    session = next(sync_session())
    try:
        source = session.get(KbSource, source_id)
        assert source is not None
        source.status = "failed"
        page = KbPage(
            source_id=source.id,
            site_id=source.site_id,
            url=FAQ_URL,
            title="Turnaround",
            content_text=TIMING_BODY,
            content_sha256="a" * 64,
            http_status=200,
            enabled=True,
            processing_status="failed",
        )
        session.add(page)
        session.commit()
        page_id = page.id
    finally:
        session.close()

    response = client.post(f"/api/kb-pages/{page_id}/retry", headers=_auth(admin))
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    session = next(sync_session())
    try:
        source = session.get(KbSource, source_id)
        assert source is not None
        assert source.retry_urls == [FAQ_URL]
    finally:
        session.close()


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


async def test_first_live_diff_lists_units_and_same_heading_change_is_changed(
    migrated_db,
) -> None:
    from app.services.kb_snapshot import begin_snapshot, promote
    from app.services.kb_source_admin import KbSourceService

    async with session_maker()() as session:
        site = await insert_site(session, f"easy-{uuid4().hex[:8]}", "SampleSite")
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
        await session.flush()
        first_id = await begin_snapshot(session, source.id)
        session.add(
            KbChunk(
                page_id=page.id,
                site_id=site.id,
                snapshot_id=first_id,
                ordinal=0,
                kind="section",
                heading=TIMING_TITLE,
                canonical_question=None,
                answer_verbatim=TIMING_BODY,
                body=TIMING_BODY,
                aliases=[],
                enabled=True,
            )
        )
        await promote(session, first_id)
        await session.commit()
        service = KbSourceService(session)
        first_diff = await service.diff_snapshots(source.id, None, None)
        assert [item["answer_verbatim"] for item in first_diff["added"]] == [TIMING_BODY]
        assert first_diff["changed"] == []
        assert first_diff["removed"] == []

        second_id = await begin_snapshot(session, source.id)
        session.add(
            KbChunk(
                page_id=page.id,
                site_id=site.id,
                snapshot_id=second_id,
                ordinal=0,
                kind="section",
                heading=TIMING_TITLE,
                canonical_question=None,
                answer_verbatim="Rapid negatives can arrive in minutes.",
                body="Rapid negatives can arrive in minutes.",
                aliases=[],
                enabled=True,
            )
        )
        await promote(session, second_id)
        await session.commit()
        second_diff = await service.diff_snapshots(source.id, first_id, second_id)
        assert second_diff["added"] == []
        assert second_diff["removed"] == []
        assert len(second_diff["changed"]) == 1
        assert second_diff["changed"][0]["before"]["answer_verbatim"] == TIMING_BODY
        assert (
            second_diff["changed"][0]["after"]["answer_verbatim"]
            == "Rapid negatives can arrive in minutes."
        )


async def test_snapshot_diff_compares_every_chunk_in_a_section(migrated_db) -> None:
    from app.services.kb_snapshot import begin_snapshot, promote

    async with session_maker()() as session:
        site = await insert_site(session, f"easy-{uuid4().hex[:8]}", "SampleSite")
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
        page = KbPage(
            source_id=source.id,
            site_id=site.id,
            url=FAQ_URL,
            title="Screening process",
            content_text="Step one. Step two.",
            content_sha256="a" * 64,
            http_status=200,
            enabled=True,
        )
        session.add(page)
        await session.flush()
        first_id = await begin_snapshot(session, source.id)
        for ordinal, answer in enumerate(("Step one.", "Step two.")):
            session.add(
                KbChunk(
                    page_id=page.id,
                    site_id=site.id,
                    snapshot_id=first_id,
                    ordinal=ordinal,
                    kind="section",
                    heading="Screening process",
                    canonical_question=None,
                    answer_verbatim=answer,
                    body=answer,
                    aliases=[],
                    enabled=True,
                )
            )
        await promote(session, first_id)
        second_id = await begin_snapshot(session, source.id)
        for ordinal, answer in enumerate(("Step one.", "Step two changed.")):
            session.add(
                KbChunk(
                    page_id=page.id,
                    site_id=site.id,
                    snapshot_id=second_id,
                    ordinal=ordinal,
                    kind="section",
                    heading="Screening process",
                    canonical_question=None,
                    answer_verbatim=answer,
                    body=answer,
                    aliases=[],
                    enabled=True,
                )
            )
        await promote(session, second_id)
        await session.commit()

        diff = await KbSourceService(session).diff_snapshots(source.id, first_id, second_id)
        assert diff["added"] == []
        assert diff["removed"] == []
        assert len(diff["changed"]) == 1
        assert diff["changed"][0]["before"]["answer_verbatim"] == "Step one.\n\nStep two."
        assert diff["changed"][0]["after"]["answer_verbatim"] == "Step one.\n\nStep two changed."
