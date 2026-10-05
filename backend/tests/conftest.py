import os
from collections.abc import Generator
from urllib.parse import urlparse

import pytest

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://chat:chat@127.0.0.1:55432/support_chat_test",
)
TEST_DB_NAME = TEST_DATABASE_URL.rsplit("/", 1)[-1]
DEFAULT_TEST_REDIS_URL = "redis://:local-dev-redis@127.0.0.1:56379/15"

os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("REDIS_URL", DEFAULT_TEST_REDIS_URL)
os.environ.setdefault("JWT_SECRET", "t" * 64)
os.environ.setdefault("WIDGET_TOKEN_SECRET", "w" * 64)
os.environ.setdefault("RATE_KEY_SECRET", "r" * 64)
os.environ.setdefault(
    "WIDGET_CSP_SERVICE_SECRET",
    "e1a4b7c0d3f6a9b2c5d8e1f4a7b0c3d6e9f2a5b8c1d4e7f0a3b6c9d2e5f8a1b4c",
)
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("STAFF_APP_ORIGIN", "http://localhost:3000")
os.environ.setdefault("WIDGET_ORIGIN", "http://widget.localhost:3000")
os.environ.setdefault("KB_INGEST_HOST_DELAY_MS", "0")
os.environ.setdefault("INTERNAL_EVAL_ENABLED", "false")


def _assert_test_database() -> None:
    if "test" not in TEST_DB_NAME:
        raise RuntimeError("Refusing to run tests against a non-test database")


def _admin_url() -> str:
    return TEST_DATABASE_URL.replace("+asyncpg", "").rsplit("/", 1)[0] + "/postgres"


def _ensure_test_database() -> None:
    import psycopg

    _assert_test_database()
    with psycopg.connect(_admin_url(), autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (TEST_DB_NAME,),
        ).fetchone()
        if exists is None:
            conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')


def _postgres_is_up() -> bool:
    import psycopg

    try:
        with psycopg.connect(_admin_url(), connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def pytest_sessionstart(session: pytest.Session) -> None:
    _assert_test_database()
    if not _postgres_is_up():
        if os.environ.get("CI"):
            raise RuntimeError("Postgres is required in CI")
        if os.environ.get("ALLOW_DB_TEST_SKIP") != "1":
            session.exitstatus = 1
            pytest.exit(
                "Postgres is required. Set ALLOW_DB_TEST_SKIP=1 to skip the backend suite.",
                returncode=1,
            )
        session.exitstatus = 0
        pytest.exit("Postgres is down; skipping backend suite", returncode=0)
    _ensure_test_database()


def _truncate_tables() -> None:
    from sqlalchemy import create_engine, text

    from app.models import Base

    sync_url = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
        if table_names:
            conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    engine.dispose()


def _assert_test_redis_url(url: str) -> None:
    parsed = urlparse(url)
    path = parsed.path or "/"
    db_index = path.rstrip("/").rsplit("/", 1)[-1] if path not in {"", "/"} else "0"
    host = (parsed.hostname or "").lower()

    if db_index == "15":
        return
    if "test" in host or "test" in path:
        return

    raise RuntimeError(
        "Refusing to FLUSHDB on non-test Redis URL "
        "(use database index 15 or a host/path marked for tests)"
    )


def _flush_redis() -> None:
    import redis as redis_sync

    url = os.environ.get("REDIS_URL", DEFAULT_TEST_REDIS_URL)
    _assert_test_redis_url(url)
    client = redis_sync.Redis.from_url(url)
    try:
        client.flushdb()
    finally:
        client.close()


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    from app.settings import reset_settings_cache

    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture(autouse=True)
def _disable_ingest_worker(monkeypatch) -> None:
    async def _noop() -> None:
        return None

    monkeypatch.setattr("app.main.start_kb_workers", _noop)
    monkeypatch.setattr("app.workers.start_kb_workers", _noop)
    monkeypatch.setattr("app.workers.kb_ingest_worker.start_ingest_worker", _noop)


@pytest.fixture(autouse=True)
def _blank_anthropic_key(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")


@pytest.fixture
def migrated_db() -> Generator:
    from alembic.config import Config

    from alembic import command
    from app.db import reset_engine
    from app.redis import reset_redis

    reset_engine()
    reset_redis()
    _flush_redis()
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    _truncate_tables()
    yield
    reset_engine()
    reset_redis()
    _flush_redis()
    _truncate_tables()


@pytest.fixture
def client() -> Generator:
    from alembic.config import Config
    from fastapi.testclient import TestClient

    from alembic import command
    from app.chat.connection_manager import connection_manager
    from app.db import reset_engine
    from app.main import app
    from app.redis import reset_redis

    reset_engine()
    connection_manager.reset()
    reset_redis()
    _flush_redis()
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    _truncate_tables()
    with TestClient(app) as test_client:
        yield test_client
    reset_engine()
    reset_redis()
    _flush_redis()
    connection_manager.reset()
    _truncate_tables()
