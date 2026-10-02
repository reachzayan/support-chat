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
DATA = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
EXISTING = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
SITES = {"samplesite": EASY, "backgroundchecks": UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")}
EC2_SITES = {"samplesite": EASY, "sampledata": DATA}

INSTANT_CHECK_BODY = "Instant Check orders are not handled in this chat."
BG_CHECKS_BODY = "Background check packages start at $19.95."
HOURS_BODY = "Most negative results are reported within 24-48 hours."
UPDATED_HOURS = "SampleSite results are usually ready in one business day."
DISCOUNT_BODY = "Use code 10BGC at checkout for 10 percent off sample services."
DOT_AGENCY_BODY = "Since you are DOT-regulated under {DOTAgency}, we will point you to the program."
DISPUTE_LOGGED_BODY = (
    "Your dispute was received on [DATE/TIME] and has been logged under reference number [NUMBER]."
)
NAMED_BODY = "Hi %customer-name%, most negative results are reported within 24-48 hours."
DRIVER_ID_BODY = (
    "For driver identifiers, we use: State initials + CDL license number (example: TX1234567)."
)
ROSTER_BODY = (
    "Roster updates are handled by our support team. Please email support@sample-site.example.com with: "
    "Driver identifier: CDL state initials + license number (example: TX1234567)"
)
INTERPRETATION_BODY = (
    "This question requires review by our Compliance Team. I will document the issue and route it "
    "for a written response."
)
PROTECTED_BODY = (
    "This matter must be handled through a protected Compliance process. I will document the "
    "contact and route it immediately."
)
DISPUTE_ID_BODY = (
    "I can document the dispute through this chat. Please identify the specific item you believe "
    "is inaccurate or incomplete."
)
VERIFIED_BODY = "Thank you. Your identity has been verified."
GREETING_BODY = "Thank you for contacting Sample Services. How may I assist you today?"


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
    assert row.livechat_website == "365instantcheck.com"
    assert row.excerpt == INSTANT_CHECK_BODY
    assert row.body == INSTANT_CHECK_BODY
    assert row.shortcut == "instant-check"
    assert row.reason is None


def test_rows_with_agent_fill_in_fields_are_not_bot_eligible() -> None:
    """Catches '{DOTAgency}' and '[DATE/TIME]' scripts being enabled for the bot on import."""
    planned = plan_import(
        [
            _csv_row(49, DOT_AGENCY_BODY, 6, '["dot_yes_agency_known"]'),
            _csv_row(100, DISPUTE_LOGGED_BODY, 4, '["dispute-logged"]'),
            _csv_row(77, NAMED_BODY, 6, '["turnaround_results"]'),
        ],
        sites_by_key=SITES,
        existing=[],
    )
    by_id = {row.livechat_id: row for row in planned}
    assert by_id[49].bot_eligible is False
    assert by_id[49].disable_reason == "Has fill-in fields — not available to the bot."
    assert by_id[100].bot_eligible is False
    assert by_id[77].bot_eligible is True
    assert by_id[77].disable_reason is None


def test_scripts_that_claim_an_agent_action_are_not_bot_eligible() -> None:
    """Catches the bot telling a visitor 'Your identity has been verified'."""
    planned = plan_import(
        [
            _csv_row(106, VERIFIED_BODY, 4, '["verified"]'),
            _csv_row(97, GREETING_BODY, 4, '["greeting"]'),
        ],
        sites_by_key=SITES,
        existing=[],
    )
    assert [row.bot_eligible for row in planned] == [False, False]


def test_a_script_that_coaches_visitors_to_share_a_license_number_is_not_bot_eligible() -> None:
    """Catches the bot inviting CDL numbers into chat, which the prompts must refuse."""
    planned = plan_import(
        [
            _csv_row(94, DRIVER_ID_BODY, 6, '["driver_identifier_format"]'),
            _csv_row(95, ROSTER_BODY, 6, '["roster_update"]'),
        ],
        sites_by_key=SITES,
        existing=[],
    )
    by_id = {row.livechat_id: row for row in planned}
    assert by_id[94].bot_eligible is False
    assert (
        by_id[94].disable_reason == "Asks visitors for a license number — not available to the bot."
    )
    # Emailing a roster change is not a chat request, so the roster answer stays available.
    assert by_id[95].bot_eligible is True


def test_instant_check_rows_are_never_bot_eligible_even_when_placed_on_samplesite() -> None:
    """Catches an Instant Check search nag being served as an SampleSite answer."""
    planned = plan_import(
        [_csv_row(501, INSTANT_CHECK_BODY, 5, '["instant-check"]')],
        sites_by_key=SITES,
        existing=[],
        remap_groups={5: EASY},
    )
    row = planned[0]
    assert row.action == "create"
    assert row.site_id == EASY
    assert row.bot_eligible is False
    assert row.disable_reason == "Instant Check content — not available to the bot."


def test_scripts_that_promise_a_written_follow_up_hand_off_to_a_specialist() -> None:
    """Catches 'I will document this and route it' being sent with nobody to route it."""
    planned = plan_import(
        [
            _csv_row(102, INTERPRETATION_BODY, 4, '["interpretation"]'),
            _csv_row(103, PROTECTED_BODY, 4, '["protected"]'),
            _csv_row(99, DISPUTE_ID_BODY, 4, '["dispute-id"]'),
            _csv_row(77, NAMED_BODY, 6, '["turnaround_results"]'),
        ],
        sites_by_key=SITES,
        existing=[],
    )
    assert {row.livechat_id: row.hands_off for row in planned} == {
        102: True,
        103: True,
        99: True,
        77: False,
    }


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


def test_background_checks_are_unmapped_when_that_website_is_not_hosted() -> None:
    """Catches Sample Services being skipped on an SampleSite + Data Solutions host."""
    planned = plan_import(
        [_csv_row(410, BG_CHECKS_BODY, 4, '["packages"]')],
        sites_by_key=EC2_SITES,
        existing=[],
    )
    assert len(planned) == 1
    row = planned[0]
    assert row.action == "unmapped"
    assert row.group == 4
    assert row.group_name == "Sample Services"
    assert row.excerpt == BG_CHECKS_BODY
    assert row.body == BG_CHECKS_BODY
    assert row.shortcut == "packages"
    assert row.livechat_website == "sample-services.example.com"
    assert row.reason is None


def test_background_checks_can_be_assigned_to_data_solutions() -> None:
    """Catches remap still dropping Sample Services instead of creating it on Data Solutions."""
    planned = plan_import(
        [_csv_row(410, BG_CHECKS_BODY, 4, '["packages"]')],
        sites_by_key=EC2_SITES,
        existing=[],
        remap_groups={4: DATA},
    )
    assert len(planned) == 1
    row = planned[0]
    assert row.action == "create"
    assert row.site_id == DATA
    assert row.shortcut == "packages"
    assert row.body == BG_CHECKS_BODY


def test_samplesite_still_maps_when_the_hosted_site_uses_a_different_key() -> None:
    """Catches SampleSite canned replies skipping because the site key is not 'samplesite'."""
    hosted = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    planned = plan_import(
        [_csv_row(200, HOURS_BODY, 6)],
        sites_by_key={"es-prod": hosted},
        sites_by_name={"samplesite": hosted},
        existing=[],
    )
    assert planned[0].action == "create"
    assert planned[0].site_id == hosted
    assert planned[0].excerpt == HOURS_BODY
    assert planned[0].livechat_website == "sample-site.example.com"


def test_commit_does_not_drop_instant_check_when_staff_omit_a_mapping(client: TestClient) -> None:
    """Catches Instant Check being skipped on commit because it is not a hardcoded SupportChat site."""
    insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_staff(ADMIN_EMAIL, "Admin", ALEX_PASSWORD, is_admin=True)
    token = login_staff(client, ADMIN_EMAIL, ALEX_PASSWORD)
    payload = _csv_bytes(
        [
            _csv_row(200, HOURS_BODY, 6),
            _csv_row(501, INSTANT_CHECK_BODY, 5, '["instant-check"]'),
        ]
    )
    commit = client.post(
        "/api/canned-replies/import",
        headers=_auth(token),
        files={"file": ("canned.csv", payload, "text/csv")},
        data={"decisions": json.dumps({"discard_ids": [], "remap_groups": {}})},
    )
    assert commit.status_code == 422
    assert commit.json()["detail"] == (
        "Choose a website for each LiveChat group, or discard those responses."
    )
    library = client.get("/api/canned-replies/library", headers=_auth(token))
    assert library.json()["items"] == []


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
    assert row["livechat_website"] == "365instantcheck.com"
    assert row["excerpt"] == INSTANT_CHECK_BODY
    assert row["reason"] is None

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


def test_preview_keeps_background_checks_copy_and_commit_can_place_it_on_data_solutions(
    client: TestClient,
) -> None:
    """Catches Sample Services vanishing on a host that has Data Solutions, not backgroundchecks."""
    easy_id = insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    data_id = insert_site("sampledata", "Data Solutions", "f" * 64, [HOST_ORIGIN])
    insert_staff(ADMIN_EMAIL, "Admin", ALEX_PASSWORD, is_admin=True)
    token = login_staff(client, ADMIN_EMAIL, ALEX_PASSWORD)
    payload = _csv_bytes(
        [
            _csv_row(200, HOURS_BODY, 6),
            _csv_row(410, BG_CHECKS_BODY, 4, '["packages"]'),
            _csv_row(501, INSTANT_CHECK_BODY, 5, '["instant-check"]'),
        ]
    )

    preview = client.post(
        "/api/canned-replies/import/preview",
        headers=_auth(token),
        files={"file": ("canned.csv", payload, "text/csv")},
    )
    assert preview.status_code == 200
    rows = preview.json()["rows"]
    easy_row = next(row for row in rows if row["livechat_id"] == 200)
    bg_row = next(row for row in rows if row["livechat_id"] == 410)
    instant_row = next(row for row in rows if row["livechat_id"] == 501)
    assert easy_row["action"] == "create"
    assert easy_row["group_name"] == "SampleSite"
    assert easy_row["livechat_website"] == "sample-site.example.com"
    assert easy_row["site_id"] == str(easy_id)
    assert bg_row["action"] == "unmapped"
    assert bg_row["group_name"] == "Sample Services"
    assert bg_row["livechat_website"] == "sample-services.example.com"
    assert bg_row["excerpt"] == BG_CHECKS_BODY
    assert bg_row["reason"] is None
    assert instant_row["action"] == "unmapped"
    assert instant_row["group_name"] == "Instant Check"
    assert instant_row["livechat_website"] == "365instantcheck.com"
    assert instant_row["excerpt"] == INSTANT_CHECK_BODY

    commit = client.post(
        "/api/canned-replies/import",
        headers=_auth(token),
        files={"file": ("canned.csv", payload, "text/csv")},
        data={
            "decisions": json.dumps(
                {
                    "discard_ids": [],
                    "remap_groups": {
                        "4": str(data_id),
                        "5": str(data_id),
                        "6": str(easy_id),
                    },
                }
            )
        },
    )
    assert commit.status_code == 200
    assert commit.json() == {"created": 3, "updated": 0, "skipped": 0}
    library = client.get("/api/canned-replies/library", headers=_auth(token))
    items = {item["shortcut"]: item for item in library.json()["items"]}
    assert items["hours"]["site_id"] == str(easy_id)
    assert items["hours"]["body"] == HOURS_BODY
    assert items["packages"]["site_id"] == str(data_id)
    assert items["packages"]["body"] == BG_CHECKS_BODY
    assert items["instant-check"]["site_id"] == str(data_id)
    assert items["instant-check"]["body"] == INSTANT_CHECK_BODY


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
