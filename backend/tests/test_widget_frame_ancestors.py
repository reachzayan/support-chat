from fastapi.testclient import TestClient

from app.models.site import Site
from app.models.user import User
from app.security.passwords import hash_password
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    insert_site,
    insert_staff,
    login_staff,
    post_bootstrap,
    sync_session,
)

LOVABLE_ORIGIN = "https://sample-preview.example.com"
SSLIP_HOST_ORIGIN = "https://host.deployment.example.com"
FIXTURE_PUBLIC_KEY = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SERVICE_SECRET = "c" * 64
ADMIN_EMAIL = "admin@example.local"
ADMIN_PASSWORD = "secret"
GREETING = "Talk to a specialist about screening."
PRIVACY = "https://example.com/privacy"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _service_headers(secret: str = SERVICE_SECRET) -> dict[str, str]:
    return {"X-SupportChat-Widget-CSP": secret}


def _lookup(
    client: TestClient,
    *,
    site_key: str = "lovable-demo",
    public_key: str = FIXTURE_PUBLIC_KEY,
    parent_origin: str = LOVABLE_ORIGIN,
    secret: str = SERVICE_SECRET,
):
    return client.post(
        "/api/internal/widget-frame-ancestors",
        headers=_service_headers(secret),
        json={
            "site_key": site_key,
            "public_key": public_key,
            "parent_origin": parent_origin,
        },
    )


def _login_admin(client: TestClient) -> str:
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
    return login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def test_exact_enabled_site_returns_only_its_requested_allowed_origin(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("WIDGET_CSP_SERVICE_SECRET", SERVICE_SECRET)
    insert_site(
        "lovable-demo",
        "Lovable demo",
        FIXTURE_PUBLIC_KEY,
        allowed_origins=[LOVABLE_ORIGIN],
    )
    insert_site(
        "sslip-host",
        "sslip host",
        "b" * 64,
        allowed_origins=[SSLIP_HOST_ORIGIN],
    )

    response = _lookup(client)

    assert response.status_code == 200
    assert response.json() == {"ancestors": [LOVABLE_ORIGIN]}
    assert response.headers["cache-control"] == "private, no-store"
    assert "access-control-allow-origin" not in response.headers


def test_site_identity_cannot_authorize_another_sites_origin(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("WIDGET_CSP_SERVICE_SECRET", SERVICE_SECRET)
    insert_site(
        "lovable-demo",
        "Lovable demo",
        FIXTURE_PUBLIC_KEY,
        allowed_origins=[LOVABLE_ORIGIN],
    )
    insert_site(
        "sslip-host",
        "sslip host",
        "b" * 64,
        allowed_origins=[SSLIP_HOST_ORIGIN],
    )

    response = _lookup(client, parent_origin=SSLIP_HOST_ORIGIN)

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_lookup_hides_unknown_mismatched_and_disabled_sites(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("WIDGET_CSP_SERVICE_SECRET", SERVICE_SECRET)
    insert_site(
        "lovable-demo",
        "Lovable demo",
        FIXTURE_PUBLIC_KEY,
        allowed_origins=[LOVABLE_ORIGIN],
    )

    unknown = _lookup(client, site_key="unknown")
    wrong_key = _lookup(client, public_key="f" * 64)

    session = next(sync_session())
    try:
        site = session.query(Site).filter_by(key="lovable-demo").one()
        site.enabled = False
        session.commit()
    finally:
        session.close()
    disabled = _lookup(client)

    for response in (unknown, wrong_key, disabled):
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}


def test_lookup_rejects_missing_or_wrong_service_secret_before_parsing_body(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("WIDGET_CSP_SERVICE_SECRET", SERVICE_SECRET)
    missing = client.post("/api/internal/widget-frame-ancestors", content=b"not-json")
    wrong = client.post(
        "/api/internal/widget-frame-ancestors",
        headers=_service_headers("x" * 64),
        content=b"not-json",
    )

    assert missing.status_code == 404
    assert wrong.status_code == 404
    assert missing.json() == wrong.json() == {"detail": "Not found"}


def test_lookup_rejects_non_ascii_service_secret_without_error(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("WIDGET_CSP_SERVICE_SECRET", SERVICE_SECRET)

    response = client.post(
        "/api/internal/widget-frame-ancestors",
        headers={"X-SupportChat-Widget-CSP": b"\xff" * 64},
        content=b"not-json",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_lookup_rejects_noncanonical_parent_origin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("WIDGET_CSP_SERVICE_SECRET", SERVICE_SECRET)
    insert_site(
        "lovable-demo",
        "Lovable demo",
        FIXTURE_PUBLIC_KEY,
        allowed_origins=[LOVABLE_ORIGIN],
    )

    response = _lookup(client, parent_origin=f"{LOVABLE_ORIGIN}/page")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_lookup_rate_limit_fails_closed_before_database_work(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("WIDGET_CSP_SERVICE_SECRET", SERVICE_SECRET)
    monkeypatch.setenv("RATE_WIDGET_CSP_IP", "1")
    insert_site(
        "lovable-demo",
        "Lovable demo",
        FIXTURE_PUBLIC_KEY,
        allowed_origins=[LOVABLE_ORIGIN],
    )

    first = _lookup(client)
    second = _lookup(client)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json() == {"detail": "Too many requests"}
    assert second.headers["cache-control"] == "private, no-store"


def test_same_admin_two_websites_do_not_share_a_chatbot(client: TestClient) -> None:
    token = _login_admin(client)
    lovable = client.post(
        "/api/sites",
        headers=_auth(token),
        json={
            "key": "lovable-demo",
            "name": "Lovable demo",
            "greeting": GREETING,
            "privacy_url": PRIVACY,
            "origins": [LOVABLE_ORIGIN],
        },
    )
    sslip = client.post(
        "/api/sites",
        headers=_auth(token),
        json={
            "key": "sslip-host",
            "name": "sslip host",
            "greeting": GREETING,
            "privacy_url": PRIVACY,
            "origins": [SSLIP_HOST_ORIGIN],
        },
    )
    assert lovable.status_code == 201
    assert sslip.status_code == 201
    lovable_body = lovable.json()
    sslip_body = sslip.json()
    assert lovable_body["public_key"] != sslip_body["public_key"]
    assert lovable_body["key"] != sslip_body["key"]
    assert lovable_body["snippet"] != sslip_body["snippet"]

    lovable_ok = post_bootstrap(
        client,
        {"site_key": lovable_body["key"], "public_key": lovable_body["public_key"]},
        origin=LOVABLE_ORIGIN,
    )
    sslip_with_lovable_snippet = post_bootstrap(
        client,
        {"site_key": lovable_body["key"], "public_key": lovable_body["public_key"]},
        origin=SSLIP_HOST_ORIGIN,
    )
    lovable_with_sslip_snippet = post_bootstrap(
        client,
        {"site_key": sslip_body["key"], "public_key": sslip_body["public_key"]},
        origin=LOVABLE_ORIGIN,
    )
    sslip_ok = post_bootstrap(
        client,
        {"site_key": sslip_body["key"], "public_key": sslip_body["public_key"]},
        origin=SSLIP_HOST_ORIGIN,
    )

    assert lovable_ok.status_code == 200
    assert lovable_ok.json()["widget"]["name"] == "Lovable demo"
    assert sslip_ok.status_code == 200
    assert sslip_ok.json()["widget"]["name"] == "sslip host"
    assert sslip_with_lovable_snippet.status_code == 403
    assert lovable_with_sslip_snippet.status_code == 403


def test_sites_api_has_no_static_frame_ancestor_contract(client: TestClient) -> None:
    insert_site(
        "lovable-demo",
        "Lovable demo",
        FIXTURE_PUBLIC_KEY,
        allowed_origins=[LOVABLE_ORIGIN],
    )
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    alex = login_staff(client)

    response = client.get("/api/sites", headers=_auth(alex))

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["origins"] == [LOVABLE_ORIGIN]
    assert "origins_missing_from_frame_ancestors" not in body["items"][0]
    assert "frame_ancestors" not in body
