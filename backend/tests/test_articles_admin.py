import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import session_maker
from app.models.article import KbArticle
from app.models.user import User
from app.security.passwords import hash_password
from app.services.kb_search import KbSearch
from tests.bot_fixtures import (
    EASY_BODY,
    EASY_TITLE,
    FAST_QUERY,
    FCRA_BODY,
    FCRA_TITLE,
    seed_brand_articles,
)
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    insert_staff,
    login_staff,
    sync_session,
)

ADMIN_EMAIL = "admin@example.local"
ADMIN_NAME = "Riley Chen"
ADMIN_PASSWORD = "secret"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _insert_admin() -> uuid.UUID:
    session = next(sync_session())
    try:
        user = User(
            email=ADMIN_EMAIL,
            display_name=ADMIN_NAME,
            password_hash=hash_password(ADMIN_PASSWORD),
            is_admin=True,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id
    finally:
        session.close()


def _login_admin(client: TestClient) -> str:
    _insert_admin()
    return login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def test_non_admin_cannot_mutate_articles_and_unauthenticated_read_is_401(
    client: TestClient,
) -> None:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    alex = login_staff(client)
    admin = _login_admin(client)
    site = client.post(
        "/api/sites",
        headers=_auth(admin),
        json={
            "key": "samplesite",
            "name": "SampleSite",
            "greeting": "Talk to a specialist about screening.",
            "privacy_url": "https://sample-site.example.com/privacy",
        },
    )
    site_id = site.json()["id"]

    assert client.get(f"/api/sites/{site_id}/articles").status_code == 401
    readable = client.get(f"/api/sites/{site_id}/articles", headers=_auth(alex))
    assert readable.status_code == 200
    assert readable.json()["items"] == []

    forbidden = client.post(
        f"/api/sites/{site_id}/articles",
        headers=_auth(alex),
        json={"title": EASY_TITLE, "body": EASY_BODY},
    )
    assert forbidden.status_code == 403
    assert client.get(f"/api/sites/{site_id}/articles", headers=_auth(alex)).json()["items"] == []


def test_admin_creates_and_disables_article_then_search_omits_that_id(
    client: TestClient,
) -> None:
    admin = _login_admin(client)
    site = client.post(
        "/api/sites",
        headers=_auth(admin),
        json={
            "key": "samplesite",
            "name": "SampleSite",
            "greeting": "Talk to a specialist about screening.",
            "privacy_url": "https://sample-site.example.com/privacy",
        },
    )
    site_id = uuid.UUID(site.json()["id"])
    created = client.post(
        f"/api/sites/{site_id}/articles",
        headers=_auth(admin),
        json={"title": EASY_TITLE, "body": EASY_BODY},
    )
    assert created.status_code == 201
    article_id = uuid.UUID(created.json()["id"])
    assert created.json()["title"] == EASY_TITLE
    assert created.json()["enabled"] is True
    assert created.json()["updated_by"] is not None

    disabled = client.patch(
        f"/api/articles/{article_id}",
        headers=_auth(admin),
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    listed = client.get(f"/api/sites/{site_id}/articles", headers=_auth(admin))
    assert listed.json()["items"][0]["enabled"] is False


def test_patch_background_checks_article_leaves_samplesite_search_unchanged(
    client: TestClient,
) -> None:
    admin = _login_admin(client)
    easy = client.post(
        "/api/sites",
        headers=_auth(admin),
        json={
            "key": "samplesite",
            "name": "SampleSite",
            "greeting": "Talk to a specialist about screening.",
            "privacy_url": "https://sample-site.example.com/privacy",
        },
    )
    bg = client.post(
        "/api/sites",
        headers=_auth(admin),
        json={
            "key": "backgroundchecks",
            "name": "Sample Services",
            "greeting": "Talk to a specialist about screening.",
            "privacy_url": "https://example.test/privacy",
        },
    )
    easy_id = uuid.UUID(easy.json()["id"])
    bg_id = uuid.UUID(bg.json()["id"])
    timing = client.post(
        f"/api/sites/{easy_id}/articles",
        headers=_auth(admin),
        json={"title": EASY_TITLE, "body": EASY_BODY},
    )
    fcra = client.post(
        f"/api/sites/{bg_id}/articles",
        headers=_auth(admin),
        json={"title": FCRA_TITLE, "body": FCRA_BODY},
    )
    timing_id = uuid.UUID(timing.json()["id"])
    rewritten = client.patch(
        f"/api/articles/{fcra.json()['id']}",
        headers=_auth(admin),
        json={"title": "Rewritten FCRA", "body": "changed", "enabled": False},
    )
    assert rewritten.status_code == 200
    easy_row = client.get(f"/api/sites/{easy_id}/articles", headers=_auth(admin)).json()["items"][0]
    assert uuid.UUID(easy_row["id"]) == timing_id
    assert easy_row["title"] == EASY_TITLE
    assert easy_row["enabled"] is True
    assert easy_row["body"] == EASY_BODY


def test_enabled_text_over_five_mib_is_rejected(client: TestClient) -> None:
    admin = _login_admin(client)
    site = client.post(
        "/api/sites",
        headers=_auth(admin),
        json={
            "key": "samplesite",
            "name": "SampleSite",
            "greeting": "Talk to a specialist about screening.",
            "privacy_url": "https://sample-site.example.com/privacy",
        },
    )
    site_id = uuid.UUID(site.json()["id"])
    five_mib = 5 * 1024 * 1024
    session = next(sync_session())
    try:
        session.add(
            KbArticle(
                site_id=site_id,
                title="Stuffed source",
                body="x" * (five_mib - 20),
                enabled=True,
            )
        )
        session.commit()
    finally:
        session.close()

    overflow = client.post(
        f"/api/sites/{site_id}/articles",
        headers=_auth(admin),
        json={"title": "One more page", "body": "y" * 40},
    )
    assert overflow.status_code == 422
    listed = client.get(f"/api/sites/{site_id}/articles", headers=_auth(admin))
    titles = [row["title"] for row in listed.json()["items"]]
    assert titles == ["Stuffed source"]


async def test_admin_disable_removes_timing_article_from_search(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, timing, _fcra = await seed_brand_articles(session)
        from app.models.kb_chunk import KbChunk
        from app.models.kb_page import KbPage

        page = await session.get(KbPage, timing.page_id)
        assert page is not None
        page.enabled = False
        chunks = (
            await session.execute(select(KbChunk).where(KbChunk.page_id == page.id))
        ).scalars()
        for chunk in chunks:
            chunk.enabled = False
        await session.commit()
        hits = await KbSearch(session).search(easy.id, FAST_QUERY)
        assert [article.id for article in hits] == []
