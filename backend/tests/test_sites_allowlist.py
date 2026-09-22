import re
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.models.site import Site
from app.models.user import User
from app.security.passwords import hash_password
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    HOST_ORIGIN,
    WIDGET_ORIGIN,
    auth_visitor,
    collect_until,
    insert_site,
    insert_staff,
    login_staff,
    post_bootstrap,
    sync_session,
    visitor_count,
)

ADMIN_EMAIL = "admin@example.local"
ADMIN_NAME = "Riley Chen"
ADMIN_PASSWORD = "secret"
FIXTURE_PUBLIC_KEY = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
EASY_KEY = "samplesite"
EASY_NAME = "SampleSite Support"
EASY_GREETING = "Talk to a specialist about screening."
EASY_PRIVACY = "https://sample-site.example.com/privacy"
EXACT_ORIGIN = "https://sample-site.example.com"
SNIPPET = (
    "<script>\n"
    f'  window.__supportchat = {{ siteKey: "{EASY_KEY}", publicKey: "{FIXTURE_PUBLIC_KEY}" }};\n'
    "</script>\n"
    f'<script async src="{WIDGET_ORIGIN}/supportchat.js"></script>'
)
NOT_FOUND = {"detail": "Not found"}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _insert_admin() -> None:
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


def _login_admin(client: TestClient) -> str:
    _insert_admin()
    return login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def _origin_count(site_id: uuid.UUID) -> int:
    session = next(sync_session())
    try:
        site = session.get(Site, site_id)
        assert site is not None
        return len(site.allowed_origins)
    finally:
        session.close()


def _site_origins(site_id: uuid.UUID) -> list[str]:
    session = next(sync_session())
    try:
        site = session.get(Site, site_id)
        assert site is not None
        return list(site.allowed_origins)
    finally:
        session.close()


def test_admin_creates_exact_origin_and_rejects_path_and_wildcard(client: TestClient) -> None:
    token = _login_admin(client)
    created = client.post(
        "/api/sites",
        headers=_auth(token),
        json={
            "key": EASY_KEY,
            "name": EASY_NAME,
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
            "origins": [EXACT_ORIGIN],
        },
    )
    assert created.status_code == 201
    site_id = created.json()["id"]
    assert created.json()["origins"] == [EXACT_ORIGIN]
    assert created.json()["key"] == EASY_KEY
    assert created.json()["public_key"]
    assert created.json()["public_key"] != "YOUR_KEY"
    assert _origin_count(uuid.UUID(site_id)) == 1

    path = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(token),
        json={"origins": [f"{EXACT_ORIGIN}/dot"]},
    )
    wildcard = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(token),
        json={"origins": ["https://*.sample-site.example.com"]},
    )
    assert path.status_code == 422
    assert wildcard.status_code == 422
    assert _origin_count(uuid.UUID(site_id)) == 1
    assert _site_origins(uuid.UUID(site_id)) == [EXACT_ORIGIN]


def test_http_www_evil_and_missing_origin_fail_bootstrap_and_create_zero_visitors(
    client: TestClient,
) -> None:
    token = _login_admin(client)
    created = client.post(
        "/api/sites",
        headers=_auth(token),
        json={
            "key": EASY_KEY,
            "name": EASY_NAME,
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
            "origins": [EXACT_ORIGIN],
        },
    )
    public_key = created.json()["public_key"]
    payload = {"site_key": EASY_KEY, "public_key": public_key}

    allowed = post_bootstrap(client, payload, origin=EXACT_ORIGIN)
    http_variant = post_bootstrap(client, payload, origin="http://sample-site.example.com")
    www = post_bootstrap(client, payload, origin="https://www.sample-site.example.com")
    evil = post_bootstrap(client, payload, origin="https://evil.test")
    missing = post_bootstrap(client, payload, origin=None)

    assert allowed.status_code == 200
    assert allowed.json()["widget"] == {
        "name": EASY_NAME,
        "greeting": EASY_GREETING,
        "privacy_url": EASY_PRIVACY,
        "bot_enabled": True,
        "human_enabled": True,
        "contact_info": [],
    }
    assert "allowed_origins" not in allowed.json()
    assert "origins" not in allowed.json()
    assert http_variant.status_code == 403
    assert www.status_code == 403
    assert evil.status_code == 403
    assert missing.status_code == 403
    assert visitor_count() == 1


def test_removing_active_origin_closes_visitor_socket_4403_on_heartbeat(
    client: TestClient,
) -> None:
    token = _login_admin(client)
    created = client.post(
        "/api/sites",
        headers=_auth(token),
        json={
            "key": EASY_KEY,
            "name": EASY_NAME,
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
            "origins": [HOST_ORIGIN],
        },
    )
    site_id = created.json()["id"]
    boot = post_bootstrap(
        client,
        {"site_key": EASY_KEY, "public_key": created.json()["public_key"]},
        origin=HOST_ORIGIN,
    )
    assert boot.status_code == 200

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, boot.json()["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        removed = client.patch(
            f"/api/sites/{site_id}",
            headers=_auth(token),
            json={"origins": []},
        )
        assert removed.status_code == 200
        assert _site_origins(uuid.UUID(site_id)) == []
        visitor.send_json({"v": 1, "type": "heartbeat"})
        with pytest.raises(WebSocketDisconnect) as closed:
            visitor.receive_json()
        assert closed.value.code == 4403


def test_removing_active_origin_closes_visitor_socket_4403_on_resume(
    client: TestClient,
) -> None:
    token = _login_admin(client)
    created = client.post(
        "/api/sites",
        headers=_auth(token),
        json={
            "key": EASY_KEY,
            "name": EASY_NAME,
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
            "origins": [HOST_ORIGIN],
        },
    )
    site_id = created.json()["id"]
    boot = post_bootstrap(
        client,
        {"site_key": EASY_KEY, "public_key": created.json()["public_key"]},
        origin=HOST_ORIGIN,
    )
    assert boot.status_code == 200

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, boot.json()["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        removed = client.patch(
            f"/api/sites/{site_id}",
            headers=_auth(token),
            json={"origins": []},
        )
        assert removed.status_code == 200
        visitor.send_json({"v": 1, "type": "resume", "last_event_id": 0})
        with pytest.raises(WebSocketDisconnect) as closed:
            visitor.receive_json()
        assert closed.value.code == 4403


def test_removing_active_origin_closes_visitor_socket_4403_on_ping(
    client: TestClient,
) -> None:
    token = _login_admin(client)
    created = client.post(
        "/api/sites",
        headers=_auth(token),
        json={
            "key": EASY_KEY,
            "name": EASY_NAME,
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
            "origins": [HOST_ORIGIN],
        },
    )
    site_id = created.json()["id"]
    boot = post_bootstrap(
        client,
        {"site_key": EASY_KEY, "public_key": created.json()["public_key"]},
        origin=HOST_ORIGIN,
    )
    assert boot.status_code == 200

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, boot.json()["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        removed = client.patch(
            f"/api/sites/{site_id}",
            headers=_auth(token),
            json={"origins": []},
        )
        assert removed.status_code == 200
        visitor.send_json({"v": 1, "type": "ping"})
        with pytest.raises(WebSocketDisconnect) as closed:
            visitor.receive_json()
        assert closed.value.code == 4403


def test_staff_read_and_admin_only_mutation(client: TestClient) -> None:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    alex = login_staff(client)
    admin = _login_admin(client)

    anonymous = client.get("/api/sites")
    assert anonymous.status_code == 401

    readable = client.get("/api/sites", headers=_auth(alex))
    assert readable.status_code == 200
    assert readable.json()["items"] == []

    forbidden = client.post(
        "/api/sites",
        headers=_auth(alex),
        json={
            "key": EASY_KEY,
            "name": EASY_NAME,
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
            "origins": [EXACT_ORIGIN],
        },
    )
    assert forbidden.status_code == 403
    listed = client.get("/api/sites", headers=_auth(alex))
    assert listed.json()["items"] == []

    created = client.post(
        "/api/sites",
        headers=_auth(admin),
        json={
            "key": EASY_KEY,
            "name": EASY_NAME,
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
            "origins": [EXACT_ORIGIN],
        },
    )
    assert created.status_code == 201
    site_id = created.json()["id"]
    alex_patch = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(alex),
        json={"name": "Hijacked"},
    )
    assert alex_patch.status_code == 403
    still = client.get("/api/sites", headers=_auth(alex))
    assert still.json()["items"][0]["name"] == EASY_NAME


def test_list_includes_fixture_snippet_without_static_csp_fields(client: TestClient) -> None:
    insert_site(
        EASY_KEY, EASY_NAME, FIXTURE_PUBLIC_KEY, allowed_origins=["https://missing.example"]
    )
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    alex = login_staff(client)

    listed = client.get("/api/sites", headers=_auth(alex))
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["snippet"] == SNIPPET
    assert item["public_key"] == FIXTURE_PUBLIC_KEY
    assert "YOUR_KEY" not in item["snippet"]
    assert "access_token" not in item["snippet"]
    assert "bootstrap_token" not in item["snippet"]
    assert "origins_missing_from_frame_ancestors" not in item
    assert "frame_ancestors" not in listed.json()
    assert listed.json()["widget_origin"] == WIDGET_ORIGIN


def test_wrong_public_key_matches_unknown_site_404_and_leaks_nothing(
    client: TestClient,
) -> None:
    insert_site(EASY_KEY, EASY_NAME, FIXTURE_PUBLIC_KEY, allowed_origins=[EXACT_ORIGIN])
    unknown = post_bootstrap(
        client,
        {"site_key": "not-a-site", "public_key": "b" * 64},
        origin=EXACT_ORIGIN,
    )
    wrong_key = post_bootstrap(
        client,
        {"site_key": EASY_KEY, "public_key": "b" * 64},
        origin=EXACT_ORIGIN,
    )
    assert unknown.status_code == 404
    assert wrong_key.status_code == 404
    assert unknown.json() == NOT_FOUND
    assert wrong_key.json() == NOT_FOUND
    assert EASY_NAME not in unknown.text
    assert EASY_NAME not in wrong_key.text
    assert visitor_count() == 0


def test_new_site_defaults_to_empty_allowlist_and_key_is_immutable(client: TestClient) -> None:
    token = _login_admin(client)
    created = client.post(
        "/api/sites",
        headers=_auth(token),
        json={
            "key": EASY_KEY,
            "name": EASY_NAME,
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
        },
    )
    assert created.status_code == 201
    site_id = created.json()["id"]
    assert created.json()["origins"] == []
    assert _origin_count(uuid.UUID(site_id)) == 0

    renamed = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(token),
        json={"key": "hijacked", "name": "SampleSite Support screening"},
    )
    assert renamed.status_code == 422
    listed = client.get("/api/sites", headers=_auth(token)).json()["items"]
    loaded = next(item for item in listed if item["id"] == site_id)
    assert loaded["key"] == EASY_KEY
    assert loaded["name"] == EASY_NAME


def test_admin_create_without_key_generates_site_and_public_keys(client: TestClient) -> None:
    admin = _login_admin(client)
    created = client.post(
        "/api/sites",
        headers=_auth(admin),
        json={
            "name": "Sample Services",
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
            "origins": [EXACT_ORIGIN],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Sample Services"
    assert re.fullmatch(r"^[a-z][a-z0-9-]{0,62}$", body["key"]) is not None
    assert body["key"].startswith("sample-services")
    assert re.fullmatch(r"^[0-9a-f]{64}$", body["public_key"]) is not None
    assert body["public_key"] != "YOUR_KEY"
    assert body["key"] in body["snippet"]
    assert body["public_key"] in body["snippet"]

    again = client.post(
        "/api/sites",
        headers=_auth(admin),
        json={
            "name": "Sample Services",
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
        },
    )
    assert again.status_code == 201
    assert again.json()["key"] != body["key"]
    assert again.json()["public_key"] != body["public_key"]


def test_admin_deletes_site_staff_forbidden_and_bootstrap_404s(client: TestClient) -> None:
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    alex = login_staff(client)
    admin = _login_admin(client)
    created = client.post(
        "/api/sites",
        headers=_auth(admin),
        json={
            "key": EASY_KEY,
            "name": EASY_NAME,
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
            "origins": [EXACT_ORIGIN],
        },
    )
    assert created.status_code == 201
    site_id = created.json()["id"]
    public_key = created.json()["public_key"]

    staff_denied = client.delete(f"/api/sites/{site_id}", headers=_auth(alex))
    assert staff_denied.status_code == 403
    still_listed = client.get("/api/sites", headers=_auth(alex))
    assert still_listed.json()["items"][0]["id"] == site_id

    deleted = client.delete(f"/api/sites/{site_id}", headers=_auth(admin))
    assert deleted.status_code == 204
    assert deleted.content == b""

    listed = client.get("/api/sites", headers=_auth(admin))
    assert listed.json()["items"] == []

    missing = client.delete(f"/api/sites/{site_id}", headers=_auth(admin))
    assert missing.status_code == 404
    assert missing.json() == NOT_FOUND

    bootstrap = post_bootstrap(
        client,
        {"site_key": EASY_KEY, "public_key": public_key},
        origin=EXACT_ORIGIN,
    )
    assert bootstrap.status_code == 404
    assert bootstrap.json() == NOT_FOUND
    assert visitor_count() == 0


def test_disabled_site_bootstrap_matches_unknown_site_404(client: TestClient) -> None:
    admin = _login_admin(client)
    created = client.post(
        "/api/sites",
        headers=_auth(admin),
        json={
            "key": EASY_KEY,
            "name": EASY_NAME,
            "greeting": EASY_GREETING,
            "privacy_url": EASY_PRIVACY,
            "origins": [EXACT_ORIGIN],
        },
    )
    assert created.status_code == 201
    assert created.json()["enabled"] is True
    site_id = created.json()["id"]
    public_key = created.json()["public_key"]
    payload = {"site_key": EASY_KEY, "public_key": public_key}

    disabled = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(admin),
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    unknown = post_bootstrap(
        client,
        {"site_key": "not-a-site", "public_key": "b" * 64},
        origin=EXACT_ORIGIN,
    )
    blocked = post_bootstrap(client, payload, origin=EXACT_ORIGIN)
    assert blocked.status_code == 404
    assert blocked.json() == NOT_FOUND
    assert blocked.json() == unknown.json()
    assert EASY_NAME not in blocked.text
    assert visitor_count() == 0

    enabled = client.patch(
        f"/api/sites/{site_id}",
        headers=_auth(admin),
        json={"enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    restored = post_bootstrap(client, payload, origin=EXACT_ORIGIN)
    assert restored.status_code == 200
    assert restored.json()["widget"]["name"] == EASY_NAME
