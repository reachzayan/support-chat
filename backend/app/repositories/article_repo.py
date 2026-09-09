from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import KbArticle


class ArticleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_enabled_for_site(self, site_id: UUID) -> list[KbArticle]:
        result = await self._session.execute(
            select(KbArticle)
            .where(KbArticle.site_id == site_id, KbArticle.enabled.is_(True))
            .order_by(KbArticle.title, KbArticle.id)
        )
        return list(result.scalars().all())

    async def list_for_site(self, site_id: UUID) -> list[KbArticle]:
        result = await self._session.execute(
            select(KbArticle)
            .where(KbArticle.site_id == site_id)
            .order_by(KbArticle.title, KbArticle.id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, article_id: UUID) -> KbArticle | None:
        return await self._session.get(KbArticle, article_id)

    async def enabled_text_bytes(self, site_id: UUID) -> int:
        result = await self._session.execute(
            select(KbArticle.title, KbArticle.body).where(
                KbArticle.site_id == site_id, KbArticle.enabled.is_(True)
            )
        )
        total = 0
        for title, body in result.all():
            total += len((title or "").encode()) + len((body or "").encode())
        return total

    async def get_enabled_for_site(self, site_id: UUID, article_id: UUID) -> KbArticle | None:
        result = await self._session.execute(
            select(KbArticle).where(
                KbArticle.id == article_id,
                KbArticle.site_id == site_id,
                KbArticle.enabled.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def search_enabled(
        self,
        site_id: UUID,
        query_norm: str,
        tsquery: str | None,
        limit: int,
    ) -> list[KbArticle]:
        exact = await self._session.execute(
            select(KbArticle)
            .where(
                KbArticle.site_id == site_id,
                KbArticle.enabled.is_(True),
                func.lower(func.btrim(KbArticle.title)) == query_norm,
            )
            .order_by(KbArticle.id)
            .limit(limit)
        )
        hits = list(exact.scalars().all())
        if hits or not tsquery:
            return hits
        ts = func.to_tsquery("english", tsquery)
        ranked = await self._session.execute(
            select(KbArticle)
            .where(
                KbArticle.site_id == site_id,
                KbArticle.enabled.is_(True),
                KbArticle.search_document.op("@@")(ts),
            )
            .order_by(func.ts_rank(KbArticle.search_document, ts).desc(), KbArticle.id)
            .limit(limit)
        )
        return list(ranked.scalars().all())
