import csv
import io
import json
from uuid import UUID

from fastapi.testclient import TestClient

from app.services.canned_import import ExistingCanned, plan_import
from tests.ws_helpers import (
    ALEX_PASSWORD,
    EASY_PUBLIC_KEY,
    HOST_ORIGIN,
    insert_site,
    insert_staff,
    login_staff,
)

ADMIN_EMAIL = "admin@example.local"

EASY = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
EXISTING = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
SITES = {"samplesite": EASY, "backgroundchecks": UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")}

INSTANT_CHECK_BODY = "Instant Check orders are not handled in this chat."
HOURS_BODY = "Most negative results are reported within 24-48 hours."
UPDATED_HOURS = "SampleSite results are usually ready in one business day."
DISCOUNT_BODY = "Use code 10BGC at checkout for 10 percent off sample services."


def _csv_row(
    livechat_id: int,
    body: str,
    group: int,
    tags: str = '["hours"]',
) -> dict[str, str]:
    return {"id": str(livechat_id), "text": body, "tags": tags, "group": str(group)}


def _existing(
    *,
    livechat_id: int | None = 200,
    body: str = HOURS_BODY,
    shortcut: str = "hours",
    site_id: UUID | None = EASY,
    aliases: tuple[str, ...] = (),
    bot_eligible: bool = True,
    suggestion_event: str | None = None,
) -> ExistingCanned:
    return ExistingCanned(
        id=EXISTING,
        site_id=site_id,
        shortcut=shortcut,
        aliases=aliases,
        external_id=livechat_id,
        body=body,
        bot_eligible=bot_eligible,
        suggestion_event=suggestion_event,
    )


def test_instant_check_rows_are_unmapped_with_the_message_visible() -> None:
    """Catches Instant Check being silently skipped with an empty excerpt."""
    planned = plan_import(
        [_csv_row(501, INSTANT_CHECK_BODY, 5, '["instant-check"]')],
        sites_by_key=SITES,
        existing=[],
    )
    assert len(planned) == 1
    row = planned[0]
    assert row.action == "unmapped"
    assert row.group == 5
    assert row.group_name == "Instant Check"
    assert row.excerpt == INSTANT_CHECK_BODY
    assert row.body == INSTANT_CHECK_BODY
    assert row.shortcut == "instant-check"
    assert row.reason == ("The LiveChat group 5 is Instant Check, which is not a SupportChat site.")


def test_unmapped_group_can_be_assigned_to_an_existing_website() -> None:
    """Catches remap still dropping Instant Check instead of creating it on SampleSite."""
    planned = plan_import(
        [_csv_row(501, INSTANT_CHECK_BODY, 5, '["instant-check"]')],
        sites_by_key=SITES,
        existing=[],
        remap_groups={5: EASY},
    )
    assert len(planned) == 1
    row = planned[0]
    assert row.action == "create"
    assert row.site_id == EASY
    assert row.shortcut == "instant-check"
    assert row.body == INSTANT_CHECK_BODY


def test_same_livechat_response_with_no_edits_is_unchanged() -> None:
    """Catches a re-import treating identical LiveChat copy as an update."""
    planned = plan_import(
        [_csv_row(200, HOURS_BODY, 6)],
        sites_by_key=SITES,
        existing=[_existing()],
    )
    assert planned[0].action == "unchanged"
    assert planned[0].existing_id == EXISTING
    assert planned[0].excerpt == HOURS_BODY


def test_same_livechat_id_with_changed_copy_is_an_update() -> None:
    """Catches a changed LiveChat body being skipped or created as a new shortcut."""
    planned = plan_import(
        [_csv_row(200, UPDATED_HOURS, 6)],
        sites_by_key=SITES,
        existing=[_existing()],
    )
    assert planned[0].action == "update"
    assert planned[0].existing_id == EXISTING
    assert planned[0].body == UPDATED_HOURS
    assert planned[0].excerpt == UPDATED_HOURS


def test_matching_shortcut_in_the_same_scope_is_an_update_even_without_livechat_id() -> None:
    """Catches a library row without external_id being duplicated by shortcut."""
    planned = plan_import(
        [_csv_row(200, UPDATED_HOURS, 6)],
        sites_by_key=SITES,
        existing=[_existing(livechat_id=None)],
    )
    assert planned[0].action == "update"
    assert planned[0].existing_id == EXISTING
    assert planned[0].body == UPDATED_HOURS


def test_discarded_livechat_ids_are_skipped() -> None:
    """Catches discard decisions still writing an update."""
    planned = plan_import(
        [_csv_row(200, UPDATED_HOURS, 6)],
        sites_by_key=SITES,
        existing=[_existing()],
        discard_ids={200},
    )
    assert planned[0].action == "skip"
    assert planned[0].reason == "Discarded."
    assert planned[0].excerpt == UPDATED_HOURS


def test_discount_code_rows_stay_in_the_library_but_are_marked_staff_only() -> None:
    """Catches discount canned replies being skipped or left bot-eligible."""
    planned = plan_import(
        [_csv_row(310, DISCOUNT_BODY, 6, '["10BGC"]')],
        sites_by_key=SITES,
        existing=[],
    )
    assert planned[0].action == "create"
    assert planned[0].bot_eligible is False
    assert planned[0].disable_reason == "Discount code — not available to the bot."
    assert planned[0].excerpt == DISCOUNT_BODY
    assert planned[0].shortcut == "10bgc"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["id", "text", "tags", "group"])
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def test_preview_keeps_instant_check_copy_and_commit_can_place_it_on_samplesite(
    client: TestClient,
) -> None:
    """Catches Instant Check being dropped on commit even after staff assign it to SampleSite."""
    easy_id = insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_staff(ADMIN_EMAIL, "Admin", ALEX_PASSWORD, is_admin=True)
    token = login_staff(client, ADMIN_EMAIL, ALEX_PASSWORD)
    payload = _csv_bytes([_csv_row(501, INSTANT_CHECK_BODY, 5, '["instant-check"]')])

    preview = client.post(
        "/api/canned-replies/import/preview",
        headers=_auth(token),
        files={"file": ("canned.csv", payload, "text/csv")},
    )
    assert preview.status_code == 200
    row = preview.json()["rows"][0]
    assert row["action"] == "unmapped"
    assert row["group_name"] == "Instant Check"
    assert row["excerpt"] == INSTANT_CHECK_BODY
    assert row["reason"] == ("The LiveChat group 5 is Instant Check, which is not a SupportChat site.")

    commit = client.post(
        "/api/canned-replies/import",
        headers=_auth(token),
        files={"file": ("canned.csv", payload, "text/csv")},
        data={"decisions": json.dumps({"discard_ids": [], "remap_groups": {"5": str(easy_id)}})},
    )
    assert commit.status_code == 200
    assert commit.json() == {"created": 1, "updated": 0, "skipped": 0}
    library = client.get("/api/canned-replies/library", headers=_auth(token))
    items = library.json()["items"]
    assert len(items) == 1
    assert items[0]["site_id"] == str(easy_id)
    assert items[0]["shortcut"] == "instant-check"
    assert items[0]["body"] == INSTANT_CHECK_BODY


def test_commit_can_leave_an_existing_response_unchanged_when_staff_discard_the_update(
    client: TestClient,
) -> None:
    """Catches a re-import overwriting library copy the specialist chose to keep."""
    easy_id = insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_staff(ADMIN_EMAIL, "Admin", ALEX_PASSWORD, is_admin=True)
    token = login_staff(client, ADMIN_EMAIL, ALEX_PASSWORD)
    first = _csv_bytes([_csv_row(200, HOURS_BODY, 6)])
    imported = client.post(
        "/api/canned-replies/import",
        headers=_auth(token),
        files={"file": ("canned.csv", first, "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["created"] == 1

    changed = _csv_bytes([_csv_row(200, UPDATED_HOURS, 6)])
    preview = client.post(
        "/api/canned-replies/import/preview",
        headers=_auth(token),
        files={"file": ("canned.csv", changed, "text/csv")},
    )
    assert preview.status_code == 200
    assert preview.json()["rows"][0]["action"] == "update"
    assert preview.json()["rows"][0]["excerpt"] == UPDATED_HOURS

    discarded = client.post(
        "/api/canned-replies/import",
        headers=_auth(token),
        files={"file": ("canned.csv", changed, "text/csv")},
        data={"decisions": json.dumps({"discard_ids": [200], "remap_groups": {}})},
    )
    assert discarded.status_code == 200
    assert discarded.json() == {"created": 0, "updated": 0, "skipped": 1}
    library = client.get("/api/canned-replies/library", headers=_auth(token))
    assert library.json()["items"][0]["body"] == HOURS_BODY
    assert library.json()["items"][0]["site_id"] == str(easy_id)


def test_discount_code_preview_names_the_disabled_response(client: TestClient) -> None:
    """Catches discount canned replies vanishing from preview or staying bot-eligible."""
    insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_staff(ADMIN_EMAIL, "Admin", ALEX_PASSWORD, is_admin=True)
    token = login_staff(client, ADMIN_EMAIL, ALEX_PASSWORD)
    payload = _csv_bytes([_csv_row(310, DISCOUNT_BODY, 6, '["10BGC"]')])
    preview = client.post(
        "/api/canned-replies/import/preview",
        headers=_auth(token),
        files={"file": ("canned.csv", payload, "text/csv")},
    )
    assert preview.status_code == 200
    row = preview.json()["rows"][0]
    assert row["action"] == "create"
    assert row["bot_eligible"] is False
    assert row["disable_reason"] == "Discount code — not available to the bot."
    assert row["excerpt"] == DISCOUNT_BODY
    commit = client.post(
        "/api/canned-replies/import",
        headers=_auth(token),
        files={"file": ("canned.csv", payload, "text/csv")},
    )
    assert commit.status_code == 200
    library = client.get("/api/canned-replies/library", headers=_auth(token))
    item = library.json()["items"][0]
    assert item["shortcut"] == "10bgc"
    assert item["bot_eligible"] is False
    assert item["body"] == DISCOUNT_BODY
