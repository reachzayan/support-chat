import csv
import io
from datetime import datetime

from tests.ws_helpers import ALEX_PASSWORD, insert_staff, login_staff


def csv_file(*rows: tuple[int, str, str]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "text", "tags", "group"])
    for external_id, body, tag in rows:
        writer.writerow([external_id, body, f'["{tag}"]', 0])
    return output.getvalue().encode()


def admin_headers(client) -> dict[str, str]:
    insert_staff("history@example.local", "History admin", ALEX_PASSWORD, is_admin=True)
    return {"Authorization": f"Bearer {login_staff(client, 'history@example.local', ALEX_PASSWORD)}"}


def upload(client, headers, name, raw, **kwargs):
    return client.post(
        "/api/canned-replies/import",
        headers=headers,
        files={"file": (name, raw, "text/csv")},
        **kwargs,
    )


def test_completed_uploads_keep_original_files_and_response_versions(client) -> None:
    headers = admin_headers(client)
    first = csv_file((101, "Results take two days.", "results"))
    second = csv_file((101, "Results take one day.", "results"))
    assert upload(client, headers, "responses-v1.csv", first).json() == {
        "created": 1,
        "updated": 0,
        "skipped": 0,
    }
    assert upload(client, headers, "responses-v2.csv", second).json() == {
        "created": 0,
        "updated": 1,
        "skipped": 0,
    }

    history = client.get("/api/canned-replies/imports", headers=headers)
    assert history.status_code == 200
    batches = history.json()["items"]
    assert [batch["filename"] for batch in batches] == ["responses-v2.csv", "responses-v1.csv"]
    assert [batch["id"] for batch in batches] == [2, 1]
    assert batches[0]["uploaded_by_name"] == "History admin"
    assert datetime.fromisoformat(batches[0]["uploaded_at"]).tzinfo is not None
    assert batches[0]["updated"] == 1
    assert batches[1]["created"] == 1

    original = client.get("/api/canned-replies/imports/1", headers=headers).json()
    latest = client.get("/api/canned-replies/imports/2", headers=headers).json()
    assert original["rows"][0]["snapshot"]["body"] == "Results take two days."
    assert latest["rows"][0]["snapshot"]["body"] == "Results take one day."
    assert original["rows"][0]["action"] == "create"
    assert latest["rows"][0]["action"] == "update"
    assert original["rows"][0]["reply_id"] == latest["rows"][0]["reply_id"]
    downloaded = client.get("/api/canned-replies/imports/1/file", headers=headers)
    assert downloaded.content == first

    reply_id = original["rows"][0]["reply_id"]
    assert client.delete(f"/api/canned-replies/{reply_id}", headers=headers).status_code == 204
    retained = client.get("/api/canned-replies/imports/1", headers=headers).json()
    assert retained["rows"][0]["reply_id"] is None
    assert retained["rows"][0]["snapshot"]["body"] == "Results take two days."


def test_preview_and_failed_imports_do_not_create_history(client) -> None:
    headers = admin_headers(client)
    valid = csv_file((101, "One day.", "results"))
    client.post(
        "/api/canned-replies/import/preview",
        headers=headers,
        files={"file": ("preview.csv", valid, "text/csv")},
    )
    assert upload(client, headers, "invalid.csv", b"not a csv").status_code == 422
    conflict = csv_file((101, "First reply.", "first"), (101, "Second reply.", "second"))
    assert upload(client, headers, "conflict.csv", conflict).status_code == 409
    assert client.get("/api/canned-replies/imports", headers=headers).json()["items"] == []
    assert client.get("/api/canned-replies/library", headers=headers).json()["items"] == []


def test_identical_reuploads_have_separate_history_and_link_unchanged_responses(client) -> None:
    headers = admin_headers(client)
    raw = csv_file((101, "One day.", "results"))
    upload(client, headers, "first.csv", raw)
    upload(client, headers, "same.csv", raw)
    history = client.get("/api/canned-replies/imports", headers=headers).json()
    assert len(history["items"]) == 2
    detail = client.get("/api/canned-replies/imports/2", headers=headers).json()
    assert detail["rows"][0]["action"] == "unchanged"
    assert (
        detail["rows"][0]["reply_id"]
        == client.get("/api/canned-replies/library", headers=headers).json()["items"][0]["id"]
    )
    assert detail["rows"][0]["snapshot"]["body"] == "One day."
    page = client.get("/api/canned-replies/imports?offset=1&limit=1", headers=headers).json()
    assert [item["filename"] for item in page["items"]] == ["first.csv"]


def test_history_requires_staff_authentication(client) -> None:
    assert client.get("/api/canned-replies/imports").status_code == 401
    assert client.get("/api/canned-replies/imports/1").status_code == 401
    assert client.get("/api/canned-replies/imports/1/file").status_code == 401
