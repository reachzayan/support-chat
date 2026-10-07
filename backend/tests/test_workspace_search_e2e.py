"""Real HTTP -> authentication -> PostgreSQL search -> exact destination reads.

No browser or screenshots. The process uses only the isolated test database.
"""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import httpx

from tests.notification_e2e_helpers import eventually, free_port, sql
from tests.ws_helpers import ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD, insert_site, insert_staff


@contextmanager
def api_server(directory):
    port = free_port()
    with (directory / "search-api.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=os.environ | {"ENABLE_BACKGROUND_WORKERS": "false"},
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False
            ) as http:

                def ready():
                    assert process.poll() is None
                    assert http.get("/health").status_code == 200

                eventually(ready)
                yield http
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_real_search_and_deep_link_outside_first_page(migrated_db, tmp_path):
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    site = insert_site("easy", "SampleSite", "public-key")
    visitor, target = uuid4(), uuid4()
    sql(
        "INSERT INTO visitors (id, site_id, resume_token_hash, name, email) VALUES (%s,%s,%s,%s,%s)",
        (visitor, site, uuid4().hex, "Zoë Archer", "zoe@example.com"),
    )
    sql(
        "INSERT INTO conversations (id, site_id, visitor_id, state, prechat_submission_id, prechat_payload_hash, last_message_at) VALUES (%s,%s,%s,'closed',%s,%s,now()-interval '2 days')",
        (target, site, visitor, uuid4(), "a" * 64),
    )
    for _ in range(55):
        sql(
            "INSERT INTO conversations (site_id, visitor_id, state, prechat_submission_id, prechat_payload_hash) VALUES (%s,%s,'closed',%s,%s)",
            (site, visitor, uuid4(), "a" * 64),
        )
    sql(
        "INSERT INTO messages (conversation_id, site_id, role, client_message_id, body) VALUES (%s,%s,'visitor',%s,%s)",
        (target, site, uuid4(), "Unique payroll reconciliation question"),
    )
    with api_server(tmp_path) as http:
        assert (
            http.post("/api/search", json={"query": "payroll", "screen": "inbox"}).status_code
            == 401
        )
        login = http.post(
            "/auth/login",
            json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD},
            headers={"Origin": "http://localhost:3000"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        first = http.get("/api/conversations/submissions?limit=50", headers=headers).json()
        assert first["has_more"] is True
        assert str(target) not in [row["id"] for row in first["items"]]
        found = http.post(
            "/api/search",
            headers=headers,
            json={"query": "payroll reconciliation", "screen": "data"},
        )
        assert found.status_code == 200
        assert found.headers["cache-control"] == "no-store"
        assert found.json()["current"][0]["href"] == f"/admin/data?conversation={target}"
        detail = http.get(f"/api/conversations/submissions/{target}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["opening_message"] == "Unique payroll reconciliation question"
        site_navigation = http.post(
            "/api/search",
            headers=headers,
            json={"query": "SampleSite site settings", "screen": "inbox"},
        ).json()
        assert site_navigation["navigation"][0]["href"] == f"/admin/sites?site={site}"
        assert (
            http.get(f"/api/conversations/{target}", headers=headers).json()["messages"][0]["body"]
            == "Unique payroll reconciliation question"
        )
