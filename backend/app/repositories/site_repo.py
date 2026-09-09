from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site import Site
from app.repositories.origins import canonicalize_origins


class SiteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        key: str,
        name: str,
        public_key: str,
        allowed_origins: list[str],
        greeting: str,
        privacy_url: str,
    ) -> Site:
        site = Site(
            key=key,
            name=name,
            public_key=public_key,
            allowed_origins=canonicalize_origins(allowed_origins),
            greeting=greeting,
            privacy_url=privacy_url,
        )
        self._session.add(site)
        await self._session.flush()
        return site

    async def get_by_key(self, key: str) -> Site | None:
        result = await self._session.execute(select(Site).where(Site.key == key))
        return result.scalar_one_or_none()

    async def get_by_id(self, site_id: UUID) -> Site | None:
        return await self._session.get(Site, site_id)

    async def list_all(self) -> list[Site]:
        result = await self._session.execute(select(Site).order_by(Site.key, Site.id))
        return list(result.scalars().all())

    async def lock_by_id(self, site_id: UUID) -> Site | None:
        result = await self._session.execute(
            select(Site)
            .where(Site.id == site_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()
