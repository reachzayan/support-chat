"""Site-level contact info (phone numbers / emails) shared by the bot."""

from fastapi.testclient import TestClient

from app.models.user import User
from app.security.passwords import hash_password
from tests.ws_helpers import login_staff, sync_session

ADMIN_EMAIL = "admin@example.local"
ADMIN_NAME = "Riley Chen"
ADMIN_PASSWORD = "secret"
EASY_KEY = "samplesite"
EASY_NAME = "SampleSite Support"
EASY_GREETING = "Talk to a specialist about screening."
EASY_PRIVACY = "https://sample-site.example.com/privacy"
WEBSITE_URL = "https://sample-site.example.com"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login_admin(client: TestClient) -> str:
    session = next(sync_session())
    try:
        session.add(
            User(
                email=ADMIN_EMAIL,
                display_name=ADMIN_NAME,
                password_hash=hash_password(ADMIN_PASSWORD),
                is_admin=True,
                is_active=True,
            )
        )
        session.commit()
    finally:
        session.close()
    return login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def _create_site(client: TestClient, token: str, **overrides) -> dict:
    payload = {
        "key": EASY_KEY,
        "name": EASY_NAME,
        "greeting": EASY_GREETING,
        "privacy_url": EASY_PRIVACY,
        "origins": [WEBSITE_URL],
    }
    payload.update(overrides)
    return client.post("/api/sites", headers=_auth(token), json=payload)


def test_create_site_without_contact_info_defaults_to_empty_list(client: TestClient) -> None:
    token = _login_admin(client)
    created = _create_site(client, token)
    assert created.status_code == 201
    assert created.json()["contact_info"] == []


def test_create_site_stores_contact_info_lines_in_order(client: TestClient) -> None:
    token = _login_admin(client)
    created = _create_site(
        client,
        token,
        contact_info=["555-123-4567", "support@sample-site.example.com"],
    )
    assert created.status_code == 201
    assert created.json()["contact_info"] == ["555-123-4567", "support@sample-site.example.com"]


def test_create_site_drops_blank_lines_and_duplicates(client: TestClient) -> None:
    token = _login_admin(client)
    created = _create_site(
        client,
        token,
        contact_info=["", "   ", "555-123-4567", "555-123-4567"],
    )
    assert created.status_code == 201
    assert created.json()["contact_info"] == ["555-123-4567"]


def test_create_site_rejects_a_contact_info_entry_over_160_chars(client: TestClient) -> None:
    token = _login_admin(client)
    created = _create_site(client, token, contact_info=["x" * 161])
    assert created.status_code == 422


def test_create_site_rejects_more_than_ten_contact_info_entries(client: TestClient) -> None:
    token = _login_admin(client)
    entries = [f"555-000-{i:04d}" for i in range(11)]
    created = _create_site(client, token, contact_info=entries)
    assert created.status_code == 422


def test_update_site_replaces_contact_info(client: TestClient) -> None:
    token = _login_admin(client)
    created = _create_site(client, token, contact_info=["555-123-4567"])
    site_id = created.json()["id"]

    patched = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(token),
        json={"contact_info": ["support@sample-site.example.com"]},
    )
    assert patched.status_code == 200
    assert patched.json()["contact_info"] == ["support@sample-site.example.com"]


def test_update_site_can_clear_contact_info(client: TestClient) -> None:
    token = _login_admin(client)
    created = _create_site(client, token, contact_info=["555-123-4567"])
    site_id = created.json()["id"]

    patched = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(token),
        json={"contact_info": []},
    )
    assert patched.status_code == 200
    assert patched.json()["contact_info"] == []
