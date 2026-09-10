"""Transfer dumps must never live in the repo or Compose init path."""

from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = BACKEND_ROOT / "docker" / "db-snapshot"
COMPOSE_FILE = BACKEND_ROOT / "docker-compose.yml"
FORBIDDEN_DOC_SUBSTRINGS = (
    "01_support_chat.sql",
    "test-password-15",
    "docker/db-snapshot",
    "export_db_snapshot",
)


def test_db_snapshot_directory_is_absent() -> None:
    assert not SNAPSHOT_DIR.exists()


def test_legacy_data_dump_and_export_script_are_absent() -> None:
    assert not (BACKEND_ROOT / "docker" / "db-snapshot" / "01_support_chat.sql").exists()
    assert not (BACKEND_ROOT / "scripts" / "export_db_snapshot.sh").exists()


def test_compose_does_not_auto_import_dumps() -> None:
    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    assert "db-snapshot" not in compose
    assert "docker-entrypoint-initdb.d" not in compose


def test_backend_docs_do_not_advertise_snapshot_credentials() -> None:
    for relative in ("README.md", "docs/install.md"):
        text = (BACKEND_ROOT / relative).read_text(encoding="utf-8")
        for needle in FORBIDDEN_DOC_SUBSTRINGS:
            assert needle not in text, f"{relative} still mentions {needle}"
