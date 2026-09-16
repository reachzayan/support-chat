"""Auto-detecting the widget install and auto-building the KB from a site's website URL."""

from fastapi.testclient import TestClient

from app.models.user import User
from app.security.passwords import hash_password
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
    created = client.post("/api/sites", headers=_auth(token), json=payload)
    return created


def _stub_fetch_html(monkeypatch, html: str) -> None:
    def fake_fetch_html(url: str, allowed_hosts: set[str], hops: int = 0) -> str:
        return html

    monkeypatch.setattr("app.services.site_admin.fetch_html", fake_fetch_html)


def test_create_site_without_website_url_leaves_install_unchecked_and_skips_kb(
    client: TestClient,
) -> None:
    token = _login_admin(client)
    created = _create_site(client, token)
    assert created.status_code == 201
    body = created.json()
    assert body["website_url"] is None
    assert body["widget_installed"] is None
    assert body["widget_checked_at"] is None

    sources = client.get(f"/api/sites/{body['id']}/kb-sources", headers=_auth(token))
    assert sources.json()["items"] == []


def test_create_site_with_website_url_auto_creates_a_queued_kb_source(
    client: TestClient, monkeypatch
) -> None:
    token = _login_admin(client)
    _stub_fetch_html(monkeypatch, "<html><body>nothing here</body></html>")
    created = _create_site(client, token, website_url=WEBSITE_URL)
    assert created.status_code == 201
    site_id = created.json()["id"]

    sources = client.get(f"/api/sites/{site_id}/kb-sources", headers=_auth(token))
    items = sources.json()["items"]
    assert len(items) == 1
    assert items[0]["mode"] == "prefix"
    assert items[0]["start_url"] == "https://sample-site.example.com/"
    assert items[0]["status"] == "queued"


def test_create_site_rejects_an_http_website_url(client: TestClient) -> None:
    token = _login_admin(client)
    created = _create_site(client, token, website_url="http://sample-site.example.com")
    assert created.status_code == 422


def test_create_site_runs_an_initial_install_check(client: TestClient, monkeypatch) -> None:
    token = _login_admin(client)
    # The snippet has not been pasted onto the real site yet, so the fetched
    # homepage HTML has no trace of our widget on the very first check.
    _stub_fetch_html(monkeypatch, "<html><body>a brand new website</body></html>")
    created = _create_site(client, token, website_url=WEBSITE_URL)
    assert created.status_code == 201
    body = created.json()
    assert body["widget_installed"] is False
    assert body["widget_checked_at"] is not None


def test_check_install_detects_the_widget_when_the_public_key_is_present(
    client: TestClient, monkeypatch
) -> None:
    token = _login_admin(client)
    _stub_fetch_html(monkeypatch, "<html><body>not installed yet</body></html>")
    created = _create_site(client, token, website_url=WEBSITE_URL)
    site_id = created.json()["id"]
    public_key = created.json()["public_key"]
    assert created.json()["widget_installed"] is False

    def fake_fetch_html_with_snippet(url: str, allowed_hosts: set[str], hops: int = 0) -> str:
        return (
            "<html><head><script>window.__supportchat = "
            f'{{ siteKey: "{EASY_KEY}", publicKey: "{public_key}" }};'
            "</script></head></html>"
        )

    monkeypatch.setattr("app.services.site_admin.fetch_html", fake_fetch_html_with_snippet)
    rechecked = client.post(f"/api/sites/{site_id}/check-install", headers=_auth(token))
    assert rechecked.status_code == 200
    assert rechecked.json()["widget_installed"] is True
    assert rechecked.json()["widget_checked_at"] is not None


def test_check_install_reports_not_installed_when_the_fetch_fails(
    client: TestClient, monkeypatch
) -> None:
    token = _login_admin(client)
    _stub_fetch_html(monkeypatch, "<html><body>installed already? no.</body></html>")
    created = _create_site(client, token, website_url=WEBSITE_URL)
    site_id = created.json()["id"]

    def fake_fetch_html_boom(url: str, allowed_hosts: set[str], hops: int = 0) -> str:
        raise RuntimeError("site is unreachable")

    monkeypatch.setattr("app.services.site_admin.fetch_html", fake_fetch_html_boom)
    rechecked = client.post(f"/api/sites/{site_id}/check-install", headers=_auth(token))
    assert rechecked.status_code == 200
    assert rechecked.json()["widget_installed"] is False


def test_staff_cannot_recheck_install(client: TestClient, monkeypatch) -> None:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    alex = login_staff(client)
    token = _login_admin(client)
    _stub_fetch_html(monkeypatch, "<html><body>pending</body></html>")
    created = _create_site(client, token, website_url=WEBSITE_URL)
    site_id = created.json()["id"]

    forbidden = client.post(f"/api/sites/{site_id}/check-install", headers=_auth(alex))
    assert forbidden.status_code == 403


def test_check_install_allows_www_when_the_saved_url_is_apex(
    client: TestClient, monkeypatch
) -> None:
    token = _login_admin(client)
    _stub_fetch_html(monkeypatch, "<html><body>pending</body></html>")
    created = _create_site(client, token, website_url=WEBSITE_URL)
    site_id = created.json()["id"]
    public_key = created.json()["public_key"]

    def fake_fetch_html(url: str, allowed_hosts: set[str], hops: int = 0) -> str:
        if "www.sample-site.example.com" not in allowed_hosts:
            raise RuntimeError("www host blocked")
        return f"<html><body>publicKey: '{public_key}'</body></html>"

    monkeypatch.setattr("app.services.site_admin.fetch_html", fake_fetch_html)
    rechecked = client.post(f"/api/sites/{site_id}/check-install", headers=_auth(token))
    assert rechecked.status_code == 200
    assert rechecked.json()["widget_installed"] is True


def test_check_install_without_a_website_url_is_rejected(client: TestClient) -> None:
    token = _login_admin(client)
    created = _create_site(client, token)
    site_id = created.json()["id"]

    rechecked = client.post(f"/api/sites/{site_id}/check-install", headers=_auth(token))
    assert rechecked.status_code == 422
    assert "website URL" in rechecked.json()["detail"]


def test_update_site_can_add_a_website_url_and_a_changed_url_resets_install_status(
    client: TestClient, monkeypatch
) -> None:
    token = _login_admin(client)
    _stub_fetch_html(monkeypatch, "<html><body>not installed</body></html>")
    created = _create_site(client, token, website_url=WEBSITE_URL)
    site_id = created.json()["id"]
    public_key = created.json()["public_key"]

    def fake_fetch_html_with_snippet(url: str, allowed_hosts: set[str], hops: int = 0) -> str:
        return f"<html><body>publicKey: '{public_key}'</body></html>"

    monkeypatch.setattr("app.services.site_admin.fetch_html", fake_fetch_html_with_snippet)
    rechecked = client.post(f"/api/sites/{site_id}/check-install", headers=_auth(token))
    assert rechecked.json()["widget_installed"] is True

    patched = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(token),
        json={"website_url": "https://other.example"},
    )
    assert patched.status_code == 200
    assert patched.json()["website_url"] == "https://other.example"
    assert patched.json()["widget_installed"] is None
    assert patched.json()["widget_checked_at"] is None
