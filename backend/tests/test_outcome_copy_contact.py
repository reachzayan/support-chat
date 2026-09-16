from app.chat.outcome_copy import BYE_LINE, THANKS_LINE, chitchat_reply, contact_line


def test_contact_line_formats_a_single_entry() -> None:
    assert contact_line(["555-123-4567"]) == "You can also reach us at 555-123-4567."


def test_contact_line_joins_multiple_entries_with_or() -> None:
    assert contact_line(["555-123-4567", "support@sample-site.example.com"]) == (
        "You can also reach us at 555-123-4567 or support@sample-site.example.com."
    )


def test_bye_reply_appends_contact_line_when_site_has_contact_info() -> None:
    reply = chitchat_reply("bye", ["555-123-4567"])
    assert reply == f"{BYE_LINE} You can also reach us at 555-123-4567."


def test_bye_reply_is_unchanged_without_contact_info() -> None:
    assert chitchat_reply("bye") == BYE_LINE
    assert chitchat_reply("bye", []) == BYE_LINE


def test_thanks_reply_does_not_gain_a_contact_line() -> None:
    assert chitchat_reply("thanks", ["555-123-4567"]) == THANKS_LINE
