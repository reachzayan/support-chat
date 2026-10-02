from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from uuid import UUID

BODY_MAX = 20_000


class CannedCsvError(Exception):
    pass


_SHORTCUT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_NON_SLUG = re.compile(r"[^a-z0-9_-]+")
_REPEAT_HYPHEN = re.compile(r"-{2,}")

EVENT_TAGS = {
    "_onstartchat_": "start_chat",
    "_onidle_": "idle",
    "_ongoodrate_": "good_rate",
    "_onbadrate_": "bad_rate",
    "_ontransferchat_": "transfer",
}

GROUP_SITE_KEYS = {4: "backgroundchecks", 6: "samplesite"}
GROUP_NAMES = {
    0: "General",
    4: "Sample Services",
    5: "Instant Check",
    6: "SampleSite",
}
GROUP_WEBSITES = {
    4: "sample-services.example.com",
    5: "365instantcheck.com",
    6: "sample-site.example.com",
}

CONVERSATIONAL_SLUGS = frozenset(
    {
        "hello",
        "bye",
        "wait",
        "help",
        "sure",
        "anytime",
        "disrupt",
        "product",
        "ticket",
        "welcome",
        "greeting",
        "inactivity",
        "stepped-away",
        "thought-experience",
        "search-feedback",
        "20",
        "10bgc",
    }
)
DISCOUNT_SLUGS = frozenset({"20", "10bgc"})
# Scripts an agent sends after doing something (verifying an ID, logging a dispute).
# The bot cannot do that thing, so it must not claim it.
AGENT_ACTION_SLUGS = frozenset({"verified", "unable-verify", "dispute-logged"})
# Coaches visitors to type a CDL number into chat. Chat prompts must refuse licence numbers.
# Row-level on purpose: "dispute-id" says "do not send your SSN" and "roster_update" asks for
# the number by email, so a pattern over the body would block the wrong rows.
LICENSE_NUMBER_SLUGS = frozenset({"driver_identifier_format"})
# Scripts that promise "I will document this and route it". Sending one opens a handoff so the
# promise is kept by a person.
HANDS_OFF_SLUGS = frozenset({"interpretation", "protected", "dispute-id"})
INSTANT_CHECK_GROUP = 5
# Agent fill-ins such as {DOTAgency} or [DATE/TIME]. The four official %variables% are not these.
_UNFILLED_FIELD = re.compile(r"\{[^{}\s][^{}]*\}|\[[A-Z][A-Z0-9 /#_-]*\]")
FILL_IN_REASON = "Has fill-in fields — not available to the bot."

REQUIRED_COLUMNS = ("id", "text", "tags", "group")


@dataclass(frozen=True)
class ExistingCanned:
    id: UUID
    site_id: UUID | None
    shortcut: str
    aliases: tuple[str, ...]
    external_id: int | None
    body: str
    bot_eligible: bool
    suggestion_event: str | None
    hands_off: bool = False


@dataclass(frozen=True)
class ImportPlanRow:
    action: str
    reason: str | None
    livechat_id: int | None
    group: int | None
    group_name: str | None
    livechat_website: str | None
    site_id: UUID | None
    existing_id: UUID | None
    shortcut: str
    aliases: tuple[str, ...]
    body: str
    suggestion_event: str | None
    bot_eligible: bool
    disable_reason: str | None
    excerpt: str
    hands_off: bool = False


def livechat_website_for(group: int | None) -> str | None:
    if group is None:
        return None
    return GROUP_WEBSITES.get(group)


def slugify_tag(raw: str) -> str | None:
    lowered = raw.strip().lower()
    if lowered in EVENT_TAGS:
        return None
    slug = _REPEAT_HYPHEN.sub("-", _NON_SLUG.sub("-", lowered)).strip("-_")
    slug = slug[:40].strip("-_")
    if not slug or not _SHORTCUT.fullmatch(slug):
        return None
    return slug


def unique_shortcut(base: str, taken: set[str]) -> str | None:
    if base not in taken:
        return base
    for index in range(2, 100):
        suffix = f"-{index}"
        candidate = f"{base[: 40 - len(suffix)]}{suffix}"
        if candidate not in taken:
            return candidate
    return None


def has_unfilled_fields(body: str) -> bool:
    return _UNFILLED_FIELD.search(body) is not None


def bot_block_reason(body: str) -> str | None:
    """Why the bot cannot use this wording even when the row is switched on."""
    return FILL_IN_REASON if has_unfilled_fields(body) else None


def hands_off_for(slugs: list[str]) -> bool:
    return any(slug in HANDS_OFF_SLUGS for slug in slugs)


def bot_eligible_for(
    suggestion_event: str | None, slugs: list[str], body: str, group: int | None = None
) -> bool:
    return disable_reason_for(suggestion_event, slugs, body, group) is None


def disable_reason_for(
    suggestion_event: str | None, slugs: list[str], body: str, group: int | None = None
) -> str | None:
    if suggestion_event is not None:
        return "Greeting or idle prompt — not available to the bot."
    if any(slug in DISCOUNT_SLUGS for slug in slugs):
        return "Discount code — not available to the bot."
    if any(slug in CONVERSATIONAL_SLUGS for slug in slugs):
        return "Conversational prompt — not available to the bot."
    if any(slug in AGENT_ACTION_SLUGS for slug in slugs):
        return "Confirms an agent action — not available to the bot."
    if any(slug in LICENSE_NUMBER_SLUGS for slug in slugs):
        return "Asks visitors for a license number — not available to the bot."
    if group == INSTANT_CHECK_GROUP:
        return "Instant Check content — not available to the bot."
    return bot_block_reason(body)


def parse_livechat_csv(raw: bytes) -> list[dict[str, str]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CannedCsvError from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CannedCsvError
    columns = {name.strip().lstrip("\ufeff") for name in reader.fieldnames if name}
    if any(column not in columns for column in REQUIRED_COLUMNS):
        raise CannedCsvError
    return [{(key or "").strip(): value or "" for key, value in row.items()} for row in reader]


def plan_import(
    rows: list[dict[str, str]],
    *,
    sites_by_key: dict[str, UUID],
    existing: list[ExistingCanned],
    remap_groups: dict[int, UUID | None] | None = None,
    discard_ids: set[int] | None = None,
    sites_by_name: dict[str, UUID] | None = None,
) -> list[ImportPlanRow]:
    by_external = {row.external_id: row for row in existing if row.external_id is not None}
    by_token: dict[tuple[UUID | None, str], ExistingCanned] = {}
    taken: dict[UUID | None, set[str]] = {}
    for row in existing:
        taken.setdefault(row.site_id, set()).update((row.shortcut, *row.aliases))
        by_token[(row.site_id, row.shortcut)] = row
        for alias in row.aliases:
            by_token.setdefault((row.site_id, alias), row)
    remaps = remap_groups or {}
    discarded = discard_ids or set()
    named = sites_by_name or {}
    return [
        _plan_row(
            raw,
            sites_by_key=sites_by_key,
            sites_by_name=named,
            by_external=by_external,
            by_token=by_token,
            taken=taken,
            remap_groups=remaps,
            discard_ids=discarded,
        )
        for raw in rows
    ]


def _plan_row(
    raw: dict[str, str],
    *,
    sites_by_key: dict[str, UUID],
    sites_by_name: dict[str, UUID],
    by_external: dict[int, ExistingCanned],
    by_token: dict[tuple[UUID | None, str], ExistingCanned],
    taken: dict[UUID | None, set[str]],
    remap_groups: dict[int, UUID | None],
    discard_ids: set[int],
) -> ImportPlanRow:
    livechat_id = _parse_int(raw.get("id", ""))
    group = _parse_int(raw.get("group", ""))
    body = (raw.get("text") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    group_name = GROUP_NAMES.get(group) if group is not None else None
    if livechat_id is None:
        return _skip(None, group, group_name, "Row is missing a LiveChat id.")
    if group is None:
        return _skip(livechat_id, None, None, "Row is missing a LiveChat group.")
    parsed = _parse_body_and_tags(livechat_id, group, group_name, body, raw.get("tags") or "[]")
    if isinstance(parsed, ImportPlanRow):
        return parsed
    slugs, suggestion_event = parsed
    excerpt = _excerpt(body)
    if livechat_id in discard_ids:
        return _skip(livechat_id, group, group_name, "Discarded.", body=body, excerpt=excerpt)
    site_id, unmapped_reason = _resolve_site(group, sites_by_key, sites_by_name, remap_groups)
    if not slugs:
        slugs = [f"lc-{livechat_id}"[:40]]
    if unmapped_reason == "unmapped":
        return _unmapped_row(livechat_id, group, group_name, slugs, suggestion_event, body, excerpt)
    return _mapped_row(
        livechat_id=livechat_id,
        group=group,
        group_name=group_name,
        site_id=site_id,
        slugs=slugs,
        suggestion_event=suggestion_event,
        body=body,
        excerpt=excerpt,
        by_external=by_external,
        by_token=by_token,
        taken=taken,
    )


def _parse_body_and_tags(
    livechat_id: int,
    group: int,
    group_name: str | None,
    body: str,
    raw_tags: str,
) -> tuple[list[str], str | None] | ImportPlanRow:
    if not body:
        return _skip(livechat_id, group, group_name, "Message is empty.")
    if len(body) > BODY_MAX:
        return _skip(
            livechat_id,
            group,
            group_name,
            f"Message is longer than {BODY_MAX:,} characters.",
            body=body[:120],
            excerpt=_excerpt(body),
        )
    try:
        tags = json.loads(raw_tags)
    except json.JSONDecodeError:
        return _skip(
            livechat_id,
            group,
            group_name,
            "Tags are not valid JSON.",
            body=body,
            excerpt=_excerpt(body),
        )
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        return _skip(
            livechat_id,
            group,
            group_name,
            "Tags must be a JSON array of strings.",
            body=body,
            excerpt=_excerpt(body),
        )
    suggestion_event = None
    slugs: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        event = EVENT_TAGS.get(tag.strip().lower())
        if event is not None:
            if suggestion_event is None:
                suggestion_event = event
            continue
        slug = slugify_tag(tag)
        if slug is None or slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug)
    return slugs, suggestion_event


def _resolve_site(
    group: int,
    sites_by_key: dict[str, UUID],
    sites_by_name: dict[str, UUID],
    remap_groups: dict[int, UUID | None],
) -> tuple[UUID | None, str | None]:
    if group in remap_groups:
        return remap_groups[group], None
    if group == 0:
        return None, None
    key = GROUP_SITE_KEYS.get(group)
    if key is not None and key in sites_by_key:
        return sites_by_key[key], None
    named = GROUP_NAMES.get(group)
    if named is not None:
        site_id = sites_by_name.get(named.casefold())
        if site_id is not None:
            return site_id, None
    return None, "unmapped"


def _unmapped_row(
    livechat_id: int,
    group: int,
    group_name: str | None,
    slugs: list[str],
    suggestion_event: str | None,
    body: str,
    excerpt: str,
) -> ImportPlanRow:
    return ImportPlanRow(
        action="unmapped",
        reason=None,
        livechat_id=livechat_id,
        group=group,
        group_name=group_name,
        livechat_website=livechat_website_for(group),
        site_id=None,
        existing_id=None,
        shortcut=slugs[0],
        aliases=tuple(slugs[1:]),
        body=body,
        suggestion_event=suggestion_event,
        bot_eligible=bot_eligible_for(suggestion_event, slugs, body, group),
        disable_reason=disable_reason_for(suggestion_event, slugs, body, group),
        excerpt=excerpt,
        hands_off=hands_off_for(slugs),
    )


def _mapped_row(
    *,
    livechat_id: int,
    group: int,
    group_name: str | None,
    site_id: UUID | None,
    slugs: list[str],
    suggestion_event: str | None,
    body: str,
    excerpt: str,
    by_external: dict[int, ExistingCanned],
    by_token: dict[tuple[UUID | None, str], ExistingCanned],
    taken: dict[UUID | None, set[str]],
) -> ImportPlanRow:
    existing_row = _match_existing(livechat_id, site_id, slugs[0], by_external, by_token)
    if existing_row is not None and existing_row.site_id != site_id:
        return _skip(
            livechat_id,
            group,
            group_name,
            "This LiveChat id is already imported in a different scope.",
            body=body,
            excerpt=excerpt,
        )
    scope_taken = taken.setdefault(site_id, set())
    reserved = set(scope_taken)
    if existing_row is not None:
        reserved.difference_update((existing_row.shortcut, *existing_row.aliases))
    shortcut = unique_shortcut(slugs[0], reserved)
    if shortcut is None:
        return _skip(
            livechat_id,
            group,
            group_name,
            "Could not build a valid shortcut from the tags.",
            body=body,
            excerpt=excerpt,
        )
    aliases = [slug for slug in slugs[1:] if slug != shortcut and slug not in reserved]
    reserved.update((shortcut, *aliases))
    scope_taken.clear()
    scope_taken.update(reserved)
    eligible = bot_eligible_for(suggestion_event, slugs, body, group)
    hands_off = hands_off_for(slugs)
    if existing_row is None:
        action = "create"
    else:
        action = _existing_action(
            existing_row,
            livechat_id,
            site_id,
            shortcut,
            aliases,
            body,
            eligible,
            suggestion_event,
            hands_off,
        )
    return ImportPlanRow(
        action=action,
        reason="Already in the library." if action == "unchanged" else None,
        livechat_id=livechat_id,
        group=group,
        group_name=group_name,
        livechat_website=livechat_website_for(group),
        site_id=site_id,
        existing_id=None if existing_row is None else existing_row.id,
        shortcut=shortcut,
        aliases=tuple(aliases),
        body=body,
        suggestion_event=suggestion_event,
        bot_eligible=eligible,
        disable_reason=disable_reason_for(suggestion_event, slugs, body, group),
        excerpt=excerpt,
        hands_off=hands_off,
    )


def _match_existing(
    livechat_id: int,
    site_id: UUID | None,
    shortcut: str,
    by_external: dict[int, ExistingCanned],
    by_token: dict[tuple[UUID | None, str], ExistingCanned],
) -> ExistingCanned | None:
    found = by_external.get(livechat_id)
    if found is not None:
        return found
    candidate = by_token.get((site_id, shortcut))
    if candidate is None:
        return None
    if candidate.external_id is not None and candidate.external_id != livechat_id:
        return None
    return candidate


def _existing_action(
    existing: ExistingCanned,
    livechat_id: int,
    site_id: UUID | None,
    shortcut: str,
    aliases: list[str],
    body: str,
    bot_eligible: bool,
    suggestion_event: str | None,
    hands_off: bool,
) -> str:
    same = (
        existing.external_id == livechat_id
        and existing.site_id == site_id
        and existing.shortcut == shortcut
        and set(existing.aliases) == set(aliases)
        and existing.body == body
        and existing.bot_eligible == bot_eligible
        and existing.suggestion_event == suggestion_event
        and existing.hands_off == hands_off
    )
    return "unchanged" if same else "update"


def _skip(
    livechat_id: int | None,
    group: int | None,
    group_name: str | None,
    reason: str,
    *,
    body: str = "",
    excerpt: str = "",
) -> ImportPlanRow:
    return ImportPlanRow(
        action="skip",
        reason=reason,
        livechat_id=livechat_id,
        group=group,
        group_name=group_name,
        livechat_website=livechat_website_for(group),
        site_id=None,
        existing_id=None,
        shortcut="",
        aliases=(),
        body=body,
        suggestion_event=None,
        bot_eligible=False,
        disable_reason=None,
        excerpt=excerpt,
    )


def _excerpt(body: str) -> str:
    return body if len(body) <= 120 else f"{body[:117]}..."


def _parse_int(value: str) -> int | None:
    stripped = value.strip()
    if not stripped.isdigit():
        return None
    return int(stripped)
