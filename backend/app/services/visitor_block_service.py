from dataclasses import dataclass
from datetime import UTC, datetime
from ipaddress import ip_address
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.state_machine import apply_event
from app.models.conversation import Conversation
from app.models.visitor_block import VisitorBlock
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.site_repo import SiteRepository
from app.repositories.visitor_block_repo import VisitorBlockRepository


@dataclass
class VisitorBlockError(Exception):
    code: str


@dataclass
class CreatedVisitorBlock:
    block: VisitorBlock
    site_name: str
    created_by_name: str
    closed: list[tuple[Conversation, str]]


class VisitorBlockService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._blocks = VisitorBlockRepository(session)
        self._sites = SiteRepository(session)
        self._conversations = ConversationRepository(session)

    async def list_blocks(self) -> list[tuple[VisitorBlock, str, str]]:
        return await self._blocks.list_with_names()

    async def create(
        self,
        site_id: UUID,
        created_by: UUID,
        created_by_name: str,
        *,
        ip: str | None,
        email: str | None,
        phone: str | None,
    ) -> CreatedVisitorBlock:
        site = await self._sites.get_by_id(site_id)
        if site is None:
            raise VisitorBlockError("not_found")
        clean_ip = _clean_ip(ip)
        clean_email = _clean_email(email)
        clean_phone = _clean_phone(phone)
        if clean_ip is None and clean_email is None and clean_phone is None:
            raise VisitorBlockError("empty")
        existing = await self._blocks.find_matching(
            site_id, ip=clean_ip, email=clean_email, phone=clean_phone
        )
        if existing is not None:
            return CreatedVisitorBlock(
                block=existing,
                site_name=site.name,
                created_by_name=created_by_name,
                closed=[],
            )
        block = await self._blocks.create(
            site_id, created_by, ip=clean_ip, email=clean_email, phone=clean_phone
        )
        closed = await self._close_matching(
            site_id, site.key, ip=clean_ip, email=clean_email, phone=clean_phone
        )
        await self._session.commit()
        return CreatedVisitorBlock(
            block=block,
            site_name=site.name,
            created_by_name=created_by_name,
            closed=closed,
        )

    async def delete(self, block_id: UUID) -> None:
        block = await self._blocks.get_by_id(block_id)
        if block is None:
            raise VisitorBlockError("not_found")
        await self._blocks.delete(block)
        await self._session.commit()

    async def _close_matching(
        self,
        site_id: UUID,
        site_key: str,
        *,
        ip: str | None,
        email: str | None,
        phone: str | None,
    ) -> list[tuple[Conversation, str]]:
        rows = await self._conversations.list_open_matching_identifiers(
            site_id, ip=ip, email=email, phone=phone
        )
        now = datetime.now(UTC)
        closed: list[tuple[Conversation, str]] = []
        for conversation in rows:
            conversation.state = apply_event(conversation.state, "end")
            conversation.closed_at = now
            conversation.active_generation_id = None
            closed.append((conversation, site_key))
        return closed


def _clean_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def _clean_phone(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_ip(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return str(ip_address(cleaned))
    except ValueError as exc:
        raise VisitorBlockError("invalid_ip") from exc
