import json
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from structlog.testing import capture_logs

from app.models.user import User
from app.security.passwords import hash_password
from tests.conftest import TEST_DATABASE_URL

LOGIN_FAILURE = "Invalid email or password"
ALEX_EMAIL = "agent@example.local"
ALEX_NAME = "Alex Morgan"
ALEX_PASSWORD = "secret"


def _sync_session() -> Iterator[Session]:
    engine = create_engine(
        TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _insert_alex(is_active: bool = True, token_version: int = 0) -> uuid.UUID:
    session = next(_sync_session())
    try:
        user = User(
            email=ALEX_EMAIL,
            display_name=ALEX_NAME,
            password_hash=hash_password(ALEX_PASSWORD),
            is_admin=False,
            is_active=is_active,
            token_version=token_version,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id
    finally:
        session.close()


def _user_count() -> int:
    session = next(_sync_session())
    try:
        return int(session.scalar(select(func.count()).select_from(User)) or 0)
    finally:
        session.close()


def _cookie_headers(response) -> list[str]:
    return response.headers.get_list("set-cookie")


def _cookie_line(response, name: str) -> str:
    prefix = f"{name}="
    for line in _cookie_headers(response):
        if line.startswith(prefix):
            return line
    raise AssertionError(f"missing Set-Cookie for {name}: {_cookie_headers(response)}")


def _cookie_value(response, name: str) -> str:
    return _cookie_line(response, name).split(";", 1)[0].split("=", 1)[1]


def _csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("supportchat_csrf")
    assert token is not None
    return {"X-CSRF-Token": token}


async def test_persists_alex_morgan_and_rejects_duplicate_normalized_email(
    client: TestClient,
) -> None:
    from sqlalchemy.exc import IntegrityError

    from app.db import session_maker
    from app.repositories.user_repo import UserRepository

    async with session_maker()() as session:
        repo = UserRepository(session)
        user = await repo.create(
            email="  Agent@example.local ",
            display_name=ALEX_NAME,
            password_hash=hash_password(ALEX_PASSWORD),
        )
        await session.commit()
        fetched = await repo.get_by_email("agent@example.local")
        assert fetched is not None
        assert fetched.id == user.id
        assert fetched.email == ALEX_EMAIL
        assert fetched.display_name == ALEX_NAME
        assert fetched.password_hash != ALEX_PASSWORD
        assert fetched.password_hash.startswith("$argon2id$")

        with pytest.raises(IntegrityError):
            await repo.create(
                email="AGENT@example.local",
                display_name="Other",
                password_hash=hash_password("other"),
            )
            await session.commit()


def test_login_sets_host_only_httponly_refresh_and_returns_alex(client: TestClient) -> None:
    user_id = _insert_alex()

    response = client.post(
        "/auth/login",
        json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": str(user_id),
        "email": ALEX_EMAIL,
        "display_name": ALEX_NAME,
        "is_admin": False,
    }
    assert isinstance(body["access_token"], str)
    assert body["access_token"] != ""

    refresh = _cookie_line(response, "supportchat_refresh")
    assert "httponly" in refresh.lower()
    assert "domain=" not in refresh.lower()
    assert "samesite=lax" in refresh.lower()
    assert "path=/auth" in refresh.lower()

    csrf = _cookie_line(response, "supportchat_csrf")
    assert "httponly" not in csrf.lower()
    assert "domain=" not in csrf.lower()

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json() == {
        "id": str(user_id),
        "email": ALEX_EMAIL,
        "display_name": ALEX_NAME,
        "is_admin": False,
    }


def test_wrong_password_is_generic_and_does_not_log_secrets(client: TestClient) -> None:
    _insert_alex()

    with capture_logs() as logs:
        response = client.post(
            "/auth/login",
            json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD + "-wrong"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": LOGIN_FAILURE}
    assert not any("supportchat_refresh=" in line.lower() for line in _cookie_headers(response))
    serialized = json.dumps(logs)
    assert ALEX_PASSWORD + "-wrong" not in serialized
    assert ALEX_PASSWORD not in serialized
    assert ALEX_EMAIL not in serialized
    assert any(entry.get("event") == "login_failed" for entry in logs)


def test_refresh_rotation_and_reuse_revokes_family(client: TestClient) -> None:
    _insert_alex()
    login = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD})
    r1 = _cookie_value(login, "supportchat_refresh")

    rotated = client.post("/auth/refresh", headers=_csrf_headers(client))
    assert rotated.status_code == 200
    r2 = _cookie_value(rotated, "supportchat_refresh")
    assert r2 != r1
    assert rotated.json()["user"]["display_name"] == ALEX_NAME

    client.cookies.set("supportchat_refresh", r1, path="/auth")
    replay = client.post("/auth/refresh", headers=_csrf_headers(client))
    assert replay.status_code == 401

    client.cookies.set("supportchat_refresh", r2, path="/auth")
    after_reuse = client.post("/auth/refresh", headers=_csrf_headers(client))
    assert after_reuse.status_code == 401


def test_csrf_mismatch_does_not_rotate_or_logout(client: TestClient) -> None:
    _insert_alex()
    login = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD})
    access = login.json()["access_token"]
    r1 = _cookie_value(login, "supportchat_refresh")

    missing = client.post("/auth/refresh")
    assert missing.status_code == 403

    mismatch = client.post("/auth/refresh", headers={"X-CSRF-Token": "not-the-cookie"})
    assert mismatch.status_code == 403

    client.cookies.set("supportchat_refresh", r1, path="/auth")
    still_valid = client.post("/auth/refresh", headers=_csrf_headers(client))
    assert still_valid.status_code == 200

    logout_mismatch = client.post("/auth/logout", headers={"X-CSRF-Token": "nope"})
    assert logout_mismatch.status_code == 403
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["display_name"] == ALEX_NAME

    change_mismatch = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {access}", "X-CSRF-Token": "nope"},
        json={"current_password": ALEX_PASSWORD, "new_password": "corrected-pass1"},
    )
    assert change_mismatch.status_code == 403
    still_old = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD})
    assert still_old.status_code == 200


def test_password_change_revokes_old_credentials(client: TestClient) -> None:
    _insert_alex()
    login = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD})
    access = login.json()["access_token"]
    new_password = "corrected-pass1"

    changed = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {access}", **_csrf_headers(client)},
        json={"current_password": ALEX_PASSWORD, "new_password": new_password},
    )
    assert changed.status_code == 200

    stale_me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert stale_me.status_code == 401

    stale_refresh = client.post("/auth/refresh", headers=_csrf_headers(client))
    assert stale_refresh.status_code == 401

    old_login = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD})
    assert old_login.status_code == 401
    assert old_login.json() == {"detail": LOGIN_FAILURE}

    new_login = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": new_password})
    assert new_login.status_code == 200
    assert new_login.json()["user"]["display_name"] == ALEX_NAME


def test_logout_increments_token_version_and_clears_refresh(client: TestClient) -> None:
    user_id = _insert_alex()
    login = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD})
    access = login.json()["access_token"]

    logout = client.post("/auth/logout", headers=_csrf_headers(client))
    assert logout.status_code == 200
    refresh_clear = _cookie_line(logout, "supportchat_refresh")
    assert (
        "max-age=0" in refresh_clear.lower()
        or "max-age=0" in refresh_clear.replace(" ", "").lower()
    )

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 401

    session = next(_sync_session())
    try:
        user = session.get(User, user_id)
        assert user is not None
        assert user.token_version == 1
    finally:
        session.close()


def test_inactive_and_stale_token_version_cannot_use_me(client: TestClient) -> None:
    user_id = _insert_alex()
    login = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD})
    access = login.json()["access_token"]

    session = next(_sync_session())
    try:
        user = session.get(User, user_id)
        assert user is not None
        user.token_version += 1
        session.commit()
    finally:
        session.close()

    stale = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert stale.status_code == 401

    inactive_id = _insert_alex_variant(email="inactive@example.local", is_active=False)
    inactive_login = client.post(
        "/auth/login",
        json={"email": "inactive@example.local", "password": ALEX_PASSWORD},
    )
    assert inactive_login.status_code == 401
    assert inactive_login.json() == {"detail": LOGIN_FAILURE}
    assert not any("supportchat_refresh=" in line.lower() for line in _cookie_headers(inactive_login))

    session = next(_sync_session())
    try:
        user = session.get(User, inactive_id)
        assert user is not None
        user.is_active = True
        session.commit()
    finally:
        session.close()

    active_login = client.post(
        "/auth/login",
        json={"email": "inactive@example.local", "password": ALEX_PASSWORD},
    )
    assert active_login.status_code == 200
    session = next(_sync_session())
    try:
        user = session.get(User, inactive_id)
        assert user is not None
        user.is_active = False
        session.commit()
    finally:
        session.close()

    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {active_login.json()['access_token']}"},
    )
    assert me.status_code == 401


def _insert_alex_variant(email: str, is_active: bool) -> uuid.UUID:
    session = next(_sync_session())
    try:
        user = User(
            email=email,
            display_name=ALEX_NAME,
            password_hash=hash_password(ALEX_PASSWORD),
            is_admin=False,
            is_active=is_active,
            token_version=0,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id
    finally:
        session.close()


def test_short_new_password_is_rejected(client: TestClient) -> None:
    _insert_alex()
    login = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD})
    access = login.json()["access_token"]
    too_short = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {access}", **_csrf_headers(client)},
        json={"current_password": ALEX_PASSWORD, "new_password": "new-secret-1"},
    )
    assert too_short.status_code == 422
    still_old = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD})
    assert still_old.status_code == 200


def test_signup_is_missing_and_does_not_create_users(client: TestClient) -> None:
    before = _user_count()
    response = client.post(
        "/auth/signup",
        json={
            "email": "new@example.local",
            "password": "anything",
            "display_name": "New Person",
        },
    )
    assert response.status_code == 404
    assert _user_count() == before
