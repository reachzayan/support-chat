"""Oracle: independently select pushed activity per user/site, without hiding in-app alerts."""

import pytest

from tests.test_notifications import auth, escalate, make_chat
from tests.test_push_notifications import RecordingSender, deliver, pending_count, subscription
from tests.test_push_notifications import push_config as push_config
from tests.ws_helpers import JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD, insert_site


def save_push(client, headers, site, *, enabled=True, scenarios=None):
    return client.put(
        "/api/notifications/preferences/push",
        headers=headers,
        json={"site_id": str(site), "enabled": enabled, "scenarios": scenarios or []},
    )


def prefs(client, headers, site):
    rows = client.get("/api/notifications/preferences", headers=headers).json()["sites"]
    return next(row for row in rows if row["site_id"] == str(site))


def test_push_preferences_are_private_and_keep_types_when_a_site_is_disabled(client):
    _, headers = auth(client)
    _, other = auth(client, JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD)
    easy = insert_site("easy", "SampleSite", "key")
    careers = insert_site("careers", "Careers", "other-key")
    response = save_push(client, headers, easy, enabled=False, scenarios=["bot", "closed"])
    assert response.status_code == 200
    assert prefs(client, headers, easy)["push"] == {
        "enabled": False,
        "scenarios": ["bot", "closed"],
    }
    assert prefs(client, headers, easy)["scenarios"]["needs_attention"] is True
    for account, site in [(headers, careers), (other, easy)]:
        assert prefs(client, account, site)["push"] == {
            "enabled": True,
            "scenarios": ["live", "needs_attention", "visitor_message"],
        }
    assert save_push(client, headers, easy, scenarios=["bot", "closed"]).status_code == 200
    assert prefs(client, headers, easy)["push"]["scenarios"] == ["bot", "closed"]


@pytest.mark.parametrize("scenarios", [["email"], ["bot", "bot"]])
def test_invalid_push_types_do_not_overwrite_the_previous_choice(client, scenarios):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "key")
    assert save_push(client, headers, site, scenarios=["closed"]).status_code == 200
    assert save_push(client, headers, site, scenarios=scenarios).status_code == 422
    assert prefs(client, headers, site)["push"] == {"enabled": True, "scenarios": ["closed"]}


def test_disabling_site_push_preserves_in_app_and_other_site_delivery(client):
    _, headers = auth(client)
    easy = insert_site("easy", "SampleSite", "key")
    careers = insert_site("careers", "Careers", "other-key")
    client.post("/api/notifications/push/subscriptions", headers=headers, json=subscription())
    assert (
        save_push(client, headers, easy, enabled=False, scenarios=["needs_attention"]).status_code
        == 200
    )
    for site in [easy, careers]:
        chat, visitor = client.portal.call(make_chat, site)
        client.portal.call(escalate, chat, visitor)
    feed = client.get("/api/notifications", headers=headers).json()
    assert feed["unread_count"] == 2
    assert {row["site_name"] for row in feed["items"]} == {"SampleSite", "Careers"}
    assert client.portal.call(pending_count) == 1
    sender = RecordingSender()
    client.portal.call(deliver, sender)
    assert [row["title"] for row in sender.delivered] == ["Careers · Needs attention"]


def test_push_can_arrive_with_in_app_disabled_and_can_be_read_when_chat_opens(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "key")
    client.post("/api/notifications/push/subscriptions", headers=headers, json=subscription())
    client.put(
        "/api/notifications/preferences",
        headers=headers,
        json={"site_id": str(site), "scenario": "needs_attention", "in_app": False},
    )
    assert save_push(client, headers, site, scenarios=["needs_attention"]).status_code == 200
    chat, visitor = client.portal.call(make_chat, site)
    client.portal.call(escalate, chat, visitor)
    feed = client.get("/api/notifications", headers=headers).json()
    assert feed["items"] == [] and feed["unread_count"] == 0
    assert feed["latest_id"] > 0
    assert client.portal.call(pending_count) == 1
    sender = RecordingSender()
    client.portal.call(deliver, sender)
    assert [row["title"] for row in sender.delivered] == ["SampleSite · Needs attention"]
    next_chat, next_visitor = client.portal.call(make_chat, site)
    client.portal.call(escalate, next_chat, next_visitor)
    through = client.get("/api/notifications", headers=headers).json()["latest_id"]
    assert (
        client.post(
            f"/api/notifications/conversations/{next_chat}/read",
            headers=headers,
            json={"through_id": through},
        ).status_code
        == 204
    )
    skipped = RecordingSender(())
    client.portal.call(deliver, skipped)
    assert skipped.delivered == []


@pytest.mark.parametrize(
    "enabled,types", [(False, ["needs_attention"]), (True, ["bot"]), (True, [])]
)
def test_changed_push_preferences_suppress_pending_jobs_without_removing_in_app(
    client, enabled, types
):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "key")
    client.post("/api/notifications/push/subscriptions", headers=headers, json=subscription())
    chat, visitor = client.portal.call(make_chat, site)
    client.portal.call(escalate, chat, visitor)
    assert client.portal.call(pending_count) == 1
    assert save_push(client, headers, site, enabled=enabled, scenarios=types).status_code == 200
    sender = RecordingSender(())
    client.portal.call(deliver, sender)
    assert sender.delivered == []
    assert client.portal.call(pending_count) == 0
    assert client.get("/api/notifications", headers=headers).json()["unread_count"] == 1
