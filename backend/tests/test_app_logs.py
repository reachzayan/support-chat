"""Application log persistence and admin dump — independent oracles."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import reset_engine, session_maker
from app.models.user import User
from app.security.passwords import hash_password
from tests.ws_helpers import login_staff, sync_session

ADMIN_EMAIL = "logs-admin@example.local"
ADMIN_PASSWORD = "secret-logs-admin-99"
STAFF_EMAIL = "logs-staff@example.local"
STAFF_PASSWORD = "secret-logs-staff-99"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _insert_user(*, email: str, password: str, is_admin: bool) -> None:
    session = next(sync_session())
    try:
        session.add(
            User(
                email=email,
                display_name="Log Tester",
                password_hash=hash_password(password),
                is_admin=is_admin,
                is_active=True,
            )
        )
        session.commit()
    finally:
        session.close()


def _login_admin(client: TestClient) -> str:
    _insert_user(email=ADMIN_EMAIL, password=ADMIN_PASSWORD, is_admin=True)
    return login_staff(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def _login_staff(client: TestClient) -> str:
    _insert_user(email=STAFF_EMAIL, password=STAFF_PASSWORD, is_admin=False)
    return login_staff(client, STAFF_EMAIL, STAFF_PASSWORD)


def _run_async(coro):
    """Run an async seed, then reset the engine so TestClient gets a fresh loop."""
    try:
        return asyncio.run(coro)
    finally:
        reset_engine()


def test_record_strips_sensitive_fields_and_persists_traceable_error(client: TestClient) -> None:
    from app.repositories.app_log_repo import AppLogRepository
    from app.services.app_log import record_app_log

    async def _go() -> None:
        async with session_maker()() as session:
            row = await record_app_log(
                session,
                level="error",
                source="backend",
                logger_name="chat.ws_visitor",
                event="visitor_message_failed",
                message="WebSocket visitor message handling failed",
                detail={
                    "conversation_id": str(uuid4()),
                    "site_key": "samplesite",
                    "error_class": "TimeoutError",
                    "password": "should-never-persist",
                    "authorization": "Bearer secret",
                    "email": "visitor@example.com",
                    "body": "SSN 123-45-6789 and transcript text",
                    "path": "/ws/visitor",
                    "status_code": 500,
                },
            )
            await session.commit()
            assert row.id is not None
            stored = await AppLogRepository(session).get(row.id)
            assert stored is not None
            assert stored.level == "error"
            assert stored.event == "visitor_message_failed"
            assert (stored.detail or {}).get("error_class") == "TimeoutError"
            assert "password" not in (stored.detail or {})
            assert "authorization" not in (stored.detail or {})
            assert "email" not in (stored.detail or {})
            assert "body" not in (stored.detail or {})
            assert stored.detail.get("site_key") == "samplesite"

    _run_async(_go())


def test_admin_lists_logs_staff_forbidden_unauthenticated_401(client: TestClient) -> None:
    from app.services.app_log import record_app_log

    async def _seed() -> None:
        async with session_maker()() as session:
            await record_app_log(
                session,
                level="warning",
                source="backend",
                logger_name="api.sites",
                event="site_update_rejected",
                message="Invalid origin rejected for site update",
                detail={"site_key": "demo", "error_class": "AdminError"},
            )
            await session.commit()

    _run_async(_seed())

    assert client.get("/api/logs").status_code == 401

    staff = _login_staff(client)
    assert client.get("/api/logs", headers=_auth(staff)).status_code == 403

    admin = _login_admin(client)
    response = client.get("/api/logs", headers=_auth(admin))
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert len(body["items"]) >= 1
    row = next(item for item in body["items"] if item["event"] == "site_update_rejected")
    assert row["level"] == "warning"
    assert "created_at" in row
    assert "message" in row


def test_dump_includes_only_last_7_days_with_timestamps(client: TestClient) -> None:
    from app.models.app_log import AppLog
    from app.services.app_log import record_app_log

    old_stamp = datetime.now(UTC) - timedelta(days=10)
    recent_event = f"recent_failure_{uuid4().hex[:8]}"
    stale_event = f"stale_failure_{uuid4().hex[:8]}"

    async def _seed() -> None:
        async with session_maker()() as session:
            await record_app_log(
                session,
                level="error",
                source="backend",
                logger_name="kb.pipeline",
                event=recent_event,
                message="Recent ingest failure",
                detail={"error_class": "FetchError", "url_host": "sample-site.example.com"},
            )
            session.add(
                AppLog(
                    level="error",
                    source="backend",
                    logger_name="kb.pipeline",
                    event=stale_event,
                    message="Stale ingest failure",
                    detail={"error_class": "FetchError"},
                    created_at=old_stamp,
                )
            )
            await session.commit()

    _run_async(_seed())
    admin = _login_admin(client)
    response = client.get("/api/logs/dump", headers=_auth(admin))
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    text = response.text
    assert recent_event in text
    assert stale_event not in text
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) >= 1
    for line in lines:
        assert line[0:4].isdigit()
        assert "T" in line[:32]


def test_frontend_client_log_endpoint_accepts_staff_errors(client: TestClient) -> None:
    staff = _login_staff(client)
    response = client.post(
        "/api/logs/client",
        headers=_auth(staff),
        json={
            "level": "error",
            "event": "ui_unhandled_rejection",
            "message": "Failed to load knowledge sources",
            "detail": {
                "path": "/admin/knowledge",
                "error_class": "TypeError",
                "stack": "TypeError: failed\n    at loadSources",
                "password": "nope",
            },
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["event"] == "ui_unhandled_rejection"
    assert "password" not in (body.get("detail") or {})

    admin = _login_admin(client)
    listed = client.get("/api/logs?source=frontend", headers=_auth(admin))
    assert listed.status_code == 200
    events = {item["event"] for item in listed.json()["items"]}
    assert "ui_unhandled_rejection" in events


def test_frontend_client_log_rejects_unknown_fields(client: TestClient) -> None:
    staff = _login_staff(client)
    response = client.post(
        "/api/logs/client",
        headers=_auth(staff),
        json={
            "level": "error",
            "event": "ui_window_error",
            "message": "Error",
            "stack": "should-not-be-accepted",
        },
    )
    assert response.status_code == 422


def test_unhandled_api_exception_is_persisted_for_admins(client: TestClient) -> None:
    from fastapi import APIRouter

    from app.main import app

    probe = APIRouter()

    @probe.get("/api/_test/boom")
    async def boom_route() -> None:
        raise RuntimeError("simulated_probe_boom")

    app.include_router(probe)
    try:
        response = client.get("/api/_test/boom")
        assert response.status_code == 500
    finally:
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/api/_test/boom"
        ]

    admin = _login_admin(client)
    listed = client.get("/api/logs?level=error", headers=_auth(admin))
    assert listed.status_code == 200
    blob = " ".join(
        f"{item.get('event', '')} {item.get('message', '')} {item.get('detail')}"
        for item in listed.json()["items"]
    )
    assert "simulated_probe_boom" in blob or "unhandled_exception" in blob
