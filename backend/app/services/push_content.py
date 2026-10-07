"""Shared copy for real chat alerts and explicitly labelled notification examples."""

from uuid import UUID

TITLES = {
    "needs_attention": "Needs attention",
    "live": "Live chat started",
    "visitor_message": "New visitor reply",
    "bot": "New bot conversation",
    "closed": "Chat closed",
}
DETAILS = {
    "needs_attention": "A visitor requested specialist help. Open the inbox to help.",
    "live": "A specialist joined this conversation. Open it to follow along.",
    "visitor_message": "A visitor replied to your chat. Open it to respond.",
    "bot": "A visitor started or resumed an assistant conversation. Open it to follow along.",
    "closed": "This conversation has ended. Open it to review.",
}
INQUIRIES = {
    "sales": "Sales inquiry",
    "results": "Results inquiry",
    "portal": "Portal support",
    "compliance": "Compliance inquiry",
    "other": "General inquiry",
}


def push_content(
    scenario: str, site_name: str, chat_id: UUID, inquiry: str | None, *, preview: bool = False
) -> dict[str, str]:
    name = " ".join(site_name.split()) or "SupportChat"
    name = name[:63] + "…" if len(name) > 64 else name
    reference = str(chat_id).replace("-", "")[:6].upper()
    category = INQUIRIES.get(inquiry, "General inquiry")
    return {
        "title": ("Preview: " if preview else "") + f"{name} · {TITLES[scenario]}",
        "body": f"{'Example chat' if preview else 'Chat'} #{reference} · {category}\n{DETAILS[scenario]}",
        "action_label": "Open inbox" if preview else "View chat",
    }


def preview_content(
    site_name: str | None = None, scenario: str = "needs_attention"
) -> dict[str, str]:
    if site_name is None:
        return {
            "title": "SupportChat · Push notification test",
            "body": "Your device is ready for chat alerts. Open SupportChat to view your inbox.",
            "action_label": "Open inbox",
        }
    return push_content(
        scenario, site_name, UUID("a1b2c300-0000-4000-8000-000000000000"), "portal", preview=True
    )
