import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canned_reply import CannedReply
from app.models.site import Site
from app.repositories.canned_reply_repo import CannedReplyRepository

_SHORTCUT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


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


def normalize_body(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not 1 <= len(normalized) <= 4000:
        raise CannedReplyError("invalid_body")
    return normalized


class CannedReplyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._replies = CannedReplyRepository(session)

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
        is_admin: bool = False,
    ) -> CannedReply:
        normalized_shortcut = normalize_shortcut(shortcut)
        normalized_body = normalize_body(body)
        self._require_admin_for_global(site_id, is_admin)
        if site_id is not None:
            await self._require_site(site_id)
        await self._raise_if_duplicate(site_id, normalized_shortcut)
        try:
            reply = await self._replies.create(
                site_id, normalized_shortcut, normalized_body, enabled
            )
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise CannedReplyError("conflict") from exc
        await self._session.refresh(reply)
        return reply

    async def update(
        self,
        reply_id: UUID,
        *,
        fields: set[str],
        site_id: UUID | None = None,
        shortcut: str | None = None,
        body: str | None = None,
        enabled: bool | None = None,
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
        target_shortcut = normalize_shortcut(shortcut) if "shortcut" in fields else reply.shortcut
        target_body = normalize_body(body) if "body" in fields else reply.body
        if target_site_id is not None:
            await self._require_site(target_site_id)
        await self._raise_if_duplicate(target_site_id, target_shortcut, exclude_id=reply.id)
        reply.site_id = target_site_id
        reply.shortcut = target_shortcut
        reply.body = target_body
        if "enabled" in fields:
            reply.enabled = enabled
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

    def _require_admin_for_global(self, site_id: UUID | None, is_admin: bool) -> None:
        if site_id is None and not is_admin:
            raise CannedReplyError("forbidden")

    async def _require_site(self, site_id: UUID) -> None:
        if await self._session.get(Site, site_id) is None:
            raise CannedReplyError("site_not_found")

    async def _raise_if_duplicate(
        self, site_id: UUID | None, shortcut: str, *, exclude_id: UUID | None = None
    ) -> None:
        existing = await self._replies.get_by_scope_shortcut(
            site_id, shortcut, exclude_id=exclude_id
        )
        if existing is not None:
            raise CannedReplyError("conflict")
