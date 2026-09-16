from fastapi.testclient import TestClient

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
ENV_ANCESTOR = "http://localhost:3000"
FIXTURE_PUBLIC_KEY = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
ADMIN_EMAIL = "admin@example.local"
ADMIN_PASSWORD = "secret"
GREETING = "Talk to a specialist about screening."
PRIVACY = "https://example.com/privacy"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


def test_frame_ancestors_for_lovable_parent_are_only_lovable(client: TestClient) -> None:
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

    listed = client.get(
        "/api/public/widget-frame-ancestors",
        params={"parent": f"{LOVABLE_ORIGIN}/pricing"},
    )

    assert listed.status_code == 200
    assert listed.json() == {"ancestors": [LOVABLE_ORIGIN]}
    assert SSLIP_HOST_ORIGIN not in listed.json()["ancestors"]
    assert ENV_ANCESTOR not in listed.json()["ancestors"]
    assert "*" not in listed.json()["ancestors"]


def test_frame_ancestors_for_sslip_parent_are_only_sslip(client: TestClient) -> None:
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

    listed = client.get(
        "/api/public/widget-frame-ancestors",
        params={"parent": SSLIP_HOST_ORIGIN},
    )

    assert listed.status_code == 200
    assert listed.json() == {"ancestors": [SSLIP_HOST_ORIGIN]}
    assert LOVABLE_ORIGIN not in listed.json()["ancestors"]


def test_unknown_parent_cannot_frame_the_widget(client: TestClient) -> None:
    insert_site(
        "lovable-demo",
        "Lovable demo",
        FIXTURE_PUBLIC_KEY,
        allowed_origins=[LOVABLE_ORIGIN],
    )

    listed = client.get(
        "/api/public/widget-frame-ancestors",
        params={"parent": "https://evil.test"},
    )

    assert listed.status_code == 200
    assert listed.json() == {"ancestors": []}


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


def test_list_sites_does_not_publish_a_shared_origin_union(client: TestClient) -> None:
    insert_site(
        "lovable-demo",
        "Lovable demo",
        FIXTURE_PUBLIC_KEY,
        allowed_origins=[LOVABLE_ORIGIN],
    )
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    alex = login_staff(client)

    listed = client.get("/api/sites", headers=_auth(alex))

    assert listed.status_code == 200
    body = listed.json()
    assert body["items"][0]["origins"] == [LOVABLE_ORIGIN]
    assert body["items"][0]["origins_missing_from_frame_ancestors"] is False
    assert LOVABLE_ORIGIN not in body["frame_ancestors"]
    assert "*" not in body["frame_ancestors"]
