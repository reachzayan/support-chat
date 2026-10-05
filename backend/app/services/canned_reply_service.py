import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canned_reply import CannedReply
from app.models.site import Site
from app.repositories.canned_reply_repo import CannedReplyRepository
from app.repositories.site_repo import SiteRepository
from app.services.canned_bot import embed_replies
from app.services.canned_import import (
    BODY_MAX,
    CannedCsvError,
    ExistingCanned,
    ImportPlanRow,
    parse_livechat_csv,
    plan_import,
)

_SHORTCUT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_SUGGESTION_EVENTS = frozenset({"start_chat", "idle", "good_rate", "bad_rate", "transfer"})
IMPORT_MAX_BYTES = 2_000_000


@dataclass
class CannedReplyError(Exception):
    code: str


def normalize_shortcut(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("#"):
        normalized = normalized[1:]
    normalized = normalized.lower()
    if not _SHORTCUT.fullmatch(normalized):
        raise CannedReplyError("invalid_shortcut")
    return normalized


def normalize_aliases(values: list[str] | None, primary: str) -> list[str]:
    aliases: list[str] = []
    seen = {primary}
    for value in values or []:
        shortcut = normalize_shortcut(value)
        if shortcut in seen:
            continue
        seen.add(shortcut)
        aliases.append(shortcut)
    return aliases


def normalize_body(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not 1 <= len(normalized) <= BODY_MAX:
        raise CannedReplyError("invalid_body")
    return normalized


class CannedReplyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._replies = CannedReplyRepository(session)
        self._sites = SiteRepository(session)

    async def list_effective(self, site_id: UUID) -> list[CannedReply]:
        await self._require_site(site_id)
        rows = await self._replies.list_general_and_site(site_id)
        site_shortcuts = {row.shortcut for row in rows if row.site_id == site_id}
        effective = [
            row
            for row in rows
            if row.enabled
            and (
                row.site_id == site_id
                or (row.site_id is None and row.shortcut not in site_shortcuts)
            )
        ]
        return sorted(effective, key=lambda row: (row.shortcut, str(row.id)))

    async def list_library(self) -> list[CannedReply]:
        return await self._replies.list_library()

    async def create(
        self,
        *,
        site_id: UUID | None,
        shortcut: str,
        body: str,
        enabled: bool = True,
        aliases: list[str] | None = None,
        bot_eligible: bool = True,
        follows_id: UUID | None = None,
        hands_off: bool = False,
        is_admin: bool = False,
        commit: bool = True,
    ) -> CannedReply:
        normalized_shortcut = normalize_shortcut(shortcut)
        normalized_aliases = normalize_aliases(aliases, normalized_shortcut)
        normalized_body = normalize_body(body)
        self._require_admin_for_global(site_id, is_admin)
        if site_id is not None:
            await self._require_site(site_id)
        await self._raise_if_tokens_taken(site_id, [normalized_shortcut, *normalized_aliases])
        await self._require_parent_in_scope(follows_id, site_id)
        try:
            reply = await self._replies.create(
                site_id,
                normalized_shortcut,
                normalized_body,
                enabled,
                aliases=normalized_aliases,
                bot_eligible=bot_eligible,
                follows_id=follows_id,
                hands_off=hands_off,
            )
            await embed_replies([reply])
            if commit:
                await self._session.commit()
            else:
                await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise CannedReplyError("conflict") from exc
        await self._session.refresh(reply)
        return reply

    async def update(  # noqa: C901
        self,
        reply_id: UUID,
        *,
        fields: set[str],
        site_id: UUID | None = None,
        shortcut: str | None = None,
        body: str | None = None,
        enabled: bool | None = None,
        aliases: list[str] | None = None,
        bot_eligible: bool | None = None,
        follows_id: UUID | None = None,
        hands_off: bool | None = None,
        is_admin: bool = False,
    ) -> CannedReply:
        if not fields:
            raise CannedReplyError("empty_update")
        reply = await self._replies.get_by_id(reply_id)
        if reply is None:
            raise CannedReplyError("not_found")
        self._require_admin_for_global(reply.site_id, is_admin)
        target_site_id = site_id if "site_id" in fields else reply.site_id
        self._require_admin_for_global(target_site_id, is_admin)
        if "shortcut" in fields and not isinstance(shortcut, str):
            raise CannedReplyError("invalid_shortcut")
        if "body" in fields and not isinstance(body, str):
            raise CannedReplyError("invalid_body")
        if "enabled" in fields and not isinstance(enabled, bool):
            raise CannedReplyError("invalid_body")
        if "bot_eligible" in fields and not isinstance(bot_eligible, bool):
            raise CannedReplyError("invalid_body")
        if "aliases" in fields and not isinstance(aliases, list):
            raise CannedReplyError("invalid_shortcut")
        if "hands_off" in fields and not isinstance(hands_off, bool):
            raise CannedReplyError("invalid_body")
        target_follows = follows_id if "follows_id" in fields else reply.follows_id
        target_shortcut = normalize_shortcut(shortcut) if "shortcut" in fields else reply.shortcut
        target_aliases = (
            normalize_aliases(aliases, target_shortcut)
            if "aliases" in fields
            else [alias for alias in reply.aliases if alias != target_shortcut]
        )
        target_body = normalize_body(body) if "body" in fields else reply.body
        if target_site_id is not None:
            await self._require_site(target_site_id)
        await self._raise_if_tokens_taken(
            target_site_id,
            [target_shortcut, *target_aliases],
            exclude_id=reply.id,
        )
        await self._require_parent_in_scope(target_follows, target_site_id, own_id=reply.id)
        reply.site_id = target_site_id
        reply.shortcut = target_shortcut
        reply.aliases = target_aliases
        reply.body = target_body
        reply.follows_id = target_follows
        if "enabled" in fields:
            reply.enabled = enabled
        if "bot_eligible" in fields:
            reply.bot_eligible = bot_eligible
        if "hands_off" in fields:
            reply.hands_off = hands_off
        await embed_replies([reply])
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise CannedReplyError("conflict") from exc
        await self._session.refresh(reply)
        return reply

    async def delete(self, reply_id: UUID, *, is_admin: bool = False) -> None:
        reply = await self._replies.get_by_id(reply_id)
        if reply is None:
            raise CannedReplyError("not_found")
        self._require_admin_for_global(reply.site_id, is_admin)
        await self._replies.delete(reply)
        await self._session.commit()

    async def preview_import(self, raw: bytes) -> list[ImportPlanRow]:
        return await self._plan_from_csv(raw)

    async def commit_import(
        self,
        raw: bytes,
        *,
        discard_ids: set[int] | None = None,
        remap_groups: dict[int, UUID | None] | None = None,
    ) -> dict[str, int]:
        if remap_groups:
            for site_id in remap_groups.values():
                if site_id is not None:
                    await self._require_site(site_id)
        planned = await self._plan_from_csv(raw, discard_ids=discard_ids, remap_groups=remap_groups)
        if any(row.action == "unmapped" for row in planned):
            raise CannedReplyError("unmapped_group")
        created = 0
        updated = 0
        skipped = 0
        changed: list[CannedReply] = []
        try:
            for row in planned:
                if row.action not in {"create", "update"}:
                    skipped += 1
                    continue
                if row.action == "update" and row.existing_id is not None:
                    reply = await self._replies.get_by_id(row.existing_id)
                    if reply is None:
                        skipped += 1
                        continue
                    reply.site_id = row.site_id
                    reply.shortcut = row.shortcut
                    reply.aliases = list(row.aliases)
                    reply.body = row.body
                    reply.suggestion_event = row.suggestion_event
                    reply.bot_eligible = row.bot_eligible
                    reply.hands_off = row.hands_off
                    reply.external_id = row.livechat_id
                    changed.append(reply)
                    updated += 1
                    continue
                reply = await self._replies.create(
                    row.site_id,
                    row.shortcut,
                    row.body,
                    True,
                    aliases=list(row.aliases),
                    bot_eligible=row.bot_eligible,
                    suggestion_event=row.suggestion_event,
                    external_id=row.livechat_id,
                    hands_off=row.hands_off,
                )
                changed.append(reply)
                created += 1
            await embed_replies(changed)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise CannedReplyError("conflict") from exc
        return {"created": created, "updated": updated, "skipped": skipped}

    async def _plan_from_csv(
        self,
        raw: bytes,
        *,
        discard_ids: set[int] | None = None,
        remap_groups: dict[int, UUID | None] | None = None,
    ) -> list[ImportPlanRow]:
        if len(raw) > IMPORT_MAX_BYTES:
            raise CannedReplyError("invalid_csv")
        try:
            parsed = parse_livechat_csv(raw)
        except CannedCsvError as exc:
            raise CannedReplyError("invalid_csv") from exc
        sites = await self._sites.list_all()
        sites_by_key = {site.key: site.id for site in sites}
        sites_by_name = {site.name.casefold(): site.id for site in sites}
        existing = [
            ExistingCanned(
                id=row.id,
                site_id=row.site_id,
                shortcut=row.shortcut,
                aliases=tuple(row.aliases or []),
                external_id=row.external_id,
                body=row.body,
                bot_eligible=row.bot_eligible,
                suggestion_event=row.suggestion_event,
                hands_off=row.hands_off,
            )
            for row in await self._replies.list_library()
        ]
        return plan_import(
            parsed,
            sites_by_key=sites_by_key,
            sites_by_name=sites_by_name,
            existing=existing,
            remap_groups=remap_groups,
            discard_ids=discard_ids,
        )

    def _require_admin_for_global(self, site_id: UUID | None, is_admin: bool) -> None:
        if site_id is None and not is_admin:
            raise CannedReplyError("forbidden")

    async def _require_site(self, site_id: UUID) -> None:
        if await self._session.get(Site, site_id) is None:
            raise CannedReplyError("site_not_found")

    async def _require_parent_in_scope(
        self, follows_id: UUID | None, site_id: UUID | None, *, own_id: UUID | None = None
    ) -> None:
        """A script can follow General wording or wording on its own website, never another's."""
        if follows_id is None:
            return
        parent = await self._replies.get_by_id(follows_id)
        if (
            parent is None
            or parent.id == own_id
            or (parent.site_id is not None and parent.site_id != site_id)
        ):
            raise CannedReplyError("invalid_follows")

    async def _raise_if_tokens_taken(
        self,
        site_id: UUID | None,
        tokens: list[str],
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        for token in tokens:
            existing = await self._replies.get_by_scope_shortcut(
                site_id, token, exclude_id=exclude_id
            )
            if existing is not None:
                raise CannedReplyError("conflict")
