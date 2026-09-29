from ipaddress import ip_address
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site import Site
from app.models.user import User
from app.models.visitor_block import VisitorBlock


class VisitorBlockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        site_id: UUID,
        created_by: UUID,
        *,
        ip: str | None,
        email: str | None,
        phone: str | None,
    ) -> VisitorBlock:
        block = VisitorBlock(
            site_id=site_id,
            created_by=created_by,
            ip=ip_address(ip) if ip else None,
            email=email,
            phone=phone,
        )
        self._session.add(block)
        await self._session.flush()
        return block

    async def get_by_id(self, block_id: UUID) -> VisitorBlock | None:
        return await self._session.get(VisitorBlock, block_id)

    async def list_with_names(self) -> list[tuple[VisitorBlock, str, str]]:
        result = await self._session.execute(
            select(VisitorBlock, Site.name, User.display_name)
            .join(Site, Site.id == VisitorBlock.site_id)
            .join(User, User.id == VisitorBlock.created_by)
            .order_by(VisitorBlock.created_at.desc(), VisitorBlock.id.desc())
        )
        return [
            (block, site_name, created_by_name)
            for block, site_name, created_by_name in result.all()
        ]

    async def is_blocked(
        self,
        site_id: UUID,
        *,
        ip: str | None,
        email: str | None,
        phone: str | None,
    ) -> bool:
        return await self.find_matching(site_id, ip=ip, email=email, phone=phone) is not None

    async def find_matching(
        self,
        site_id: UUID,
        *,
        ip: str | None,
        email: str | None,
        phone: str | None,
    ) -> VisitorBlock | None:
        matches = _identifier_matches(ip=ip, email=email, phone=phone)
        if not matches:
            return None
        result = await self._session.execute(
            select(VisitorBlock)
            .where(VisitorBlock.site_id == site_id, or_(*matches))
            .order_by(VisitorBlock.created_at.desc(), VisitorBlock.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def delete(self, block: VisitorBlock) -> None:
        await self._session.delete(block)
        await self._session.flush()


def _identifier_matches(*, ip: str | None, email: str | None, phone: str | None) -> list:
    matches = []
    if ip:
        matches.append(VisitorBlock.ip == ip)
    if email:
        matches.append(VisitorBlock.email == email.strip().lower())
    if phone:
        matches.append(VisitorBlock.phone == phone.strip())
    return matches
