from fastapi.testclient import TestClient

from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    BG_PUBLIC_KEY,
    EASY_PUBLIC_KEY,
    HOST_ORIGIN,
    insert_site,
    insert_staff,
    login_staff,
)

ADMIN_EMAIL = "admin@example.local"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_non_admin_staff_manages_website_responses_and_cannot_create_global(
    client: TestClient,
) -> None:
    """Catches a site override falling back to General after it is disabled."""
    easy_id = insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    background_id = insert_site(
        "backgroundchecks", "Sample Services", BG_PUBLIC_KEY, [HOST_ORIGIN]
    )
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    insert_staff(ADMIN_EMAIL, "Admin", ALEX_PASSWORD, is_admin=True)
    staff = login_staff(client)
    admin = login_staff(client, ADMIN_EMAIL, ALEX_PASSWORD)

    denied = client.post(
        "/api/canned-replies",
        headers=_auth(staff),
        json={
            "site_id": None,
            "shortcut": "hours",
            "body": "Most negative results are reported within 24-48 hours.",
        },
    )
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Forbidden"}

    general = client.post(
        "/api/canned-replies",
        headers=_auth(admin),
        json={
            "site_id": None,
            "shortcut": " #Hours ",
            "body": " Most negative results are reported within 24-48 hours. ",
            "enabled": True,
        },
    )
    assert general.status_code == 201
    general_body = general.json()
    assert general_body["site_id"] is None
    assert general_body["shortcut"] == "hours"
    assert general_body["body"] == "Most negative results are reported within 24-48 hours."
    assert general_body["enabled"] is True

    privacy = client.post(
        "/api/canned-replies",
        headers=_auth(admin),
        json={
            "site_id": None,
            "shortcut": "privacy",
            "body": "Please review our privacy notice.",
        },
    )
    assert privacy.status_code == 201

    override = client.post(
        "/api/canned-replies",
        headers=_auth(staff),
        json={
            "site_id": str(easy_id),
            "shortcut": "hours",
            "body": "SampleSite results are usually ready in one business day.",
            "enabled": False,
        },
    )
    assert override.status_code == 201

    easy = client.get("/api/canned-replies", params={"site_id": str(easy_id)}, headers=_auth(staff))
    background = client.get(
        "/api/canned-replies", params={"site_id": str(background_id)}, headers=_auth(staff)
    )
    assert easy.status_code == 200
    assert easy.json()["items"] == [
        {"shortcut": "privacy", "body": "Please review our privacy notice.", "scope": "general"}
    ]
    assert background.status_code == 200
    assert background.json()["items"] == [
        {
            "shortcut": "hours",
            "body": "Most negative results are reported within 24-48 hours.",
            "scope": "general",
        },
        {"shortcut": "privacy", "body": "Please review our privacy notice.", "scope": "general"},
    ]

    library = client.get("/api/canned-replies/library", headers=_auth(staff))
    assert library.status_code == 200
    rows = library.json()["items"]
    assert len(rows) == 3
    disabled = next(row for row in rows if row["id"] == override.json()["id"])
    assert disabled["site_id"] == str(easy_id)
    assert disabled["enabled"] is False


def test_canned_response_rejects_duplicate_shortcuts_and_invalid_updates(
    client: TestClient,
) -> None:
    """Catches case-insensitive duplicate shortcuts and an empty update silently succeeding."""
    easy_id = insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    token = login_staff(client)

    created = client.post(
        "/api/canned-replies",
        headers=_auth(token),
        json={"site_id": str(easy_id), "shortcut": "hours", "body": "One business day."},
    )
    assert created.status_code == 201
    duplicate = client.post(
        "/api/canned-replies",
        headers=_auth(token),
        json={"site_id": str(easy_id), "shortcut": "#HOURS", "body": "Another reply."},
    )
    assert duplicate.status_code == 409
    assert (
        duplicate.json()["detail"] == "A response with this shortcut already exists in this scope."
    )

    empty_update = client.patch(
        f"/api/canned-replies/{created.json()['id']}", headers=_auth(token), json={}
    )
    assert empty_update.status_code == 422
    assert empty_update.json()["detail"] == "Provide at least one field to update."

    updated = client.patch(
        f"/api/canned-replies/{created.json()['id']}",
        headers=_auth(token),
        json={"body": "\r\nUpdated response.\r\n", "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["body"] == "Updated response."
    assert updated.json()["enabled"] is False


def test_deleting_a_canned_response_removes_it_and_404s_on_repeat(client: TestClient) -> None:
    """Catches a delete route that reports success without removing the row, or 500s when repeated."""
    insert_staff(ADMIN_EMAIL, "Admin", ALEX_PASSWORD, is_admin=True)
    token = login_staff(client, ADMIN_EMAIL, ALEX_PASSWORD)

    created = client.post(
        "/api/canned-replies",
        headers=_auth(token),
        json={"site_id": None, "shortcut": "privacy", "body": "Please review our privacy notice."},
    )
    assert created.status_code == 201
    reply_id = created.json()["id"]

    deleted = client.delete(f"/api/canned-replies/{reply_id}", headers=_auth(token))
    assert deleted.status_code == 204

    library = client.get("/api/canned-replies/library", headers=_auth(token))
    assert library.json()["items"] == []

    repeat = client.delete(f"/api/canned-replies/{reply_id}", headers=_auth(token))
    assert repeat.status_code == 404
    assert repeat.json()["detail"] == "Not found"


def test_canned_response_management_requires_authenticated_staff(client: TestClient) -> None:
    """Catches an accidental public canned-response management endpoint."""
    denied = client.get("/api/canned-replies/library")
    assert denied.status_code == 401
    assert denied.json()["detail"] == "Not authenticated"
