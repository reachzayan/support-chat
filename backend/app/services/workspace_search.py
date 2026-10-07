"""Workspace destinations and ranked record projections; no private keys in results."""

import unicodedata
from typing import Literal
from urllib.parse import urlencode

from pydantic import BaseModel

from app.repositories.workspace_search_repo import WorkspaceSearchRepository

Screen = Literal[
    "inbox",
    "data",
    "sites",
    "knowledge",
    "canned-responses",
    "suggested-faqs",
    "blocked",
    "logs",
    "status",
    "notifications",
    "settings",
]
DESTINATIONS = [
    ("inbox", "Inbox", "chats conversations live bot needs attention"),
    ("data", "Data", "submissions forms contacts export"),
    ("sites", "Sites", "site websites site settings widget"),
    ("knowledge", "Knowledge base", "knowledge sources pages articles documents"),
    ("canned-responses", "Canned responses", "canned replies responses shortcuts"),
    ("suggested-faqs", "Suggested FAQs", "suggested faqs gaps unanswered questions"),
    ("blocked", "Blocked visitors", "blocked visitors unblock"),
    ("logs", "Logs", "logs errors diagnostics"),
    (
        "status",
        "Status",
        "status health services uptime redis postgres database api worker latency incidents",
    ),
    (
        "notifications",
        "Notification settings",
        "notifications notification push sound alerts preferences",
    ),
    ("settings", "Account settings", "account settings profile password theme appearance"),
]
SITE_DESTINATIONS = {
    "sites": ("Site settings", "site"),
    "knowledge": ("Knowledge base", "site"),
    "canned-responses": ("Canned responses", "scope"),
    "suggested-faqs": ("Suggested FAQs", "site"),
    "notifications": ("Notification settings", "site"),
    "inbox": ("Inbox", "site"),
}


def normalize(value):
    return " ".join(
        "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
        .lower()
        .split()
    )


class SearchItem(BaseModel):
    id: str
    screen: Screen
    title: str
    description: str
    href: str
    kind: str


class SearchResults(BaseModel):
    current: list[SearchItem]
    navigation: list[SearchItem]
    other: list[SearchItem]


def record_params(kind, row):
    item_id = str(row["id"])
    if kind == "conversation":
        return {"conversation": item_id}
    if kind == "response":
        return {"scope": str(row["site_id"]) if row["site_id"] else "general", "response": item_id}
    if kind in {"page", "source", "answer"}:
        params = {"site": str(row["site_id"]), "source": str(row["extra"])}
        if kind == "page":
            params["page"] = item_id
        if kind == "answer":
            params.update({"page": str(row["page_id"]), "chunk": item_id})
        return params
    if kind == "gap":
        return {"site": str(row["site_id"]), "view": str(row["extra"]), "gap": item_id}
    return {kind: item_id}


class WorkspaceSearch:
    def __init__(self, session):
        self.repo = WorkspaceSearchRepository(session)

    async def search(self, query: str, screen: Screen, admin: bool) -> SearchResults:
        query = normalize(query).lstrip("#")
        terms = query.split()
        allowed = [d for d in DESTINATIONS if admin or d[0] != "logs"]
        navigation = [
            SearchItem(
                id=f"nav:{key}",
                screen=key,
                title=title,
                description="Open workspace view",
                href=f"/admin/{key}",
                kind="navigation",
            )
            for key, title, aliases in allowed
            if not terms or all(t in normalize(title + " " + aliases) for t in terms)
        ]
        if len(query) < 2:
            return SearchResults(current=[], navigation=navigation, other=[])
        plain_sites = await self.repo.sites(terms)
        navigation = await self.site_navigation(terms, allowed, plain_sites, navigation)
        items = []
        for row in plain_sites:
            items.append(
                SearchItem(
                    id=f"site:{row['id']}",
                    screen="sites",
                    title=row["name"],
                    description=row["website_url"] or row["key"],
                    href=f"/admin/sites?site={row['id']}",
                    kind="site",
                )
            )
        for kind, target, row in await self.repo.records(terms, screen, admin):
            item_id = str(row["id"])
            params = record_params(kind, row)
            context = " · ".join(
                str(row.get(k) or "") for k in ("site_name", "status") if row.get(k)
            )
            excerpt = " ".join((row.get("excerpt") or "").split())
            items.append(
                SearchItem(
                    id=f"{kind}:{item_id}",
                    screen=target,
                    title=row["title"] or "Untitled",
                    description=" · ".join(filter(None, [context, excerpt]))[:260],
                    href=f"/admin/{target}?{urlencode(params)}",
                    kind=kind,
                )
            )
        # Exact titles, then title prefixes, then content. Stable tie order from repositories.
        items.sort(
            key=lambda item: (
                0
                if normalize(item.title).lstrip("#") == query
                else 1
                if normalize(item.title).lstrip("#").startswith(query)
                else 2
            )
        )
        unique_nav = list({item.id: item for item in navigation}.values())
        return SearchResults(
            current=[i for i in items if i.screen == screen][:12],
            navigation=unique_nav[:12],
            other=[i for i in items if i.screen != screen][:12],
        )

    async def site_navigation(self, terms, allowed, plain_sites, navigation):
        # Recognize destination phrases separately from the entity name.
        intents = []
        for key, title, aliases in allowed:
            if key not in SITE_DESTINATIONS:
                continue
            words = set(normalize(title + " " + aliases).split())
            if not any(t in words for t in terms):
                continue
            remainder = [
                t
                for t in terms
                if t not in words
                and t not in {"on", "the", "for", "view", "open", "go", "to", "settings"}
            ]
            if remainder != terms and remainder:
                intents.append((key, remainder))
        for key, remainder in intents:
            for row in await self.repo.sites(remainder):
                label, param = SITE_DESTINATIONS[key]
                navigation.append(
                    SearchItem(
                        id=f"nav:{key}:{row['id']}",
                        screen=key,
                        title=f"{row['name']} · {label}",
                        description=f"Open {label.lower()} for this site",
                        href=f"/admin/{key}?{urlencode({param: str(row['id'])})}",
                        kind="navigation",
                    )
                )
        for row in plain_sites:
            for key in ("sites", "knowledge", "notifications"):
                label, param = SITE_DESTINATIONS[key]
                navigation.append(
                    SearchItem(
                        id=f"nav:{key}:{row['id']}",
                        screen=key,
                        title=f"{row['name']} · {label}",
                        description="Open site workspace",
                        href=f"/admin/{key}?{urlencode({param: str(row['id'])})}",
                        kind="navigation",
                    )
                )
        return navigation
