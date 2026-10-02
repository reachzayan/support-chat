from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canned_reply import CannedReply


class CannedReplyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        site_id: UUID | None,
        shortcut: str,
        body: str,
        enabled: bool,
        *,
        aliases: list[str] | None = None,
        bot_eligible: bool = True,
        suggestion_event: str | None = None,
        external_id: int | None = None,
        follows_id: UUID | None = None,
        hands_off: bool = False,
    ) -> CannedReply:
        reply = CannedReply(
            site_id=site_id,
            shortcut=shortcut,
            body=body,
            enabled=enabled,
            aliases=list(aliases or []),
            bot_eligible=bot_eligible,
            suggestion_event=suggestion_event,
            external_id=external_id,
            follows_id=follows_id,
            hands_off=hands_off,
        )
        self._session.add(reply)
        await self._session.flush()
        return reply

    async def get_by_id(self, reply_id: UUID) -> CannedReply | None:
        return await self._session.get(CannedReply, reply_id)

    async def get_by_scope_shortcut(
        self, site_id: UUID | None, shortcut: str, *, exclude_id: UUID | None = None
    ) -> CannedReply | None:
        conditions = [
            or_(
                func.lower(CannedReply.shortcut) == shortcut,
                CannedReply.aliases.contains([shortcut]),
            )
        ]
        if site_id is None:
            conditions.append(CannedReply.site_id.is_(None))
        else:
            conditions.append(CannedReply.site_id == site_id)
        if exclude_id is not None:
            conditions.append(CannedReply.id != exclude_id)
        result = await self._session.execute(select(CannedReply).where(*conditions))
        return result.scalar_one_or_none()

    async def list_library(self) -> list[CannedReply]:
        result = await self._session.execute(
            select(CannedReply).order_by(
                CannedReply.site_id.is_not(None),
                CannedReply.site_id,
                CannedReply.shortcut,
                CannedReply.id,
            )
        )
        return list(result.scalars().all())

    async def list_general_and_site(self, site_id: UUID) -> list[CannedReply]:
        result = await self._session.execute(
            select(CannedReply)
            .where(CannedReply.site_id.is_(None) | (CannedReply.site_id == site_id))
            .order_by(CannedReply.shortcut, CannedReply.id)
        )
        return list(result.scalars().all())

    async def list_bot_eligible(self, site_id: UUID) -> list[CannedReply]:
        result = await self._session.execute(
            select(CannedReply).where(
                CannedReply.enabled.is_(True),
                CannedReply.bot_eligible.is_(True),
                CannedReply.site_id.is_(None) | (CannedReply.site_id == site_id),
            )
        )
        rows = list(result.scalars().all())
        site_shortcuts = {row.shortcut for row in rows if row.site_id == site_id}
        return [
            row
            for row in rows
            if row.site_id == site_id
            or (row.site_id is None and row.shortcut not in site_shortcuts)
        ]

    async def closest_to(
        self, site_id: UUID, embedder_id: str, vector: list[float]
    ) -> tuple[CannedReply, float] | None:
        """The nearest embedded reply on this website or General, with its cosine similarity."""
        distance = CannedReply.embedding.cosine_distance(vector)
        result = await self._session.execute(
            select(CannedReply, distance)
            .where(
                CannedReply.enabled.is_(True),
                CannedReply.embedding.is_not(None),
                CannedReply.embedder_id == embedder_id,
                CannedReply.site_id.is_(None) | (CannedReply.site_id == site_id),
            )
            .order_by(distance, CannedReply.id)
            .limit(1)
        )
        row = result.first()
        return None if row is None else (row[0], 1.0 - float(row[1]))

    async def list_needing_embedding(self, embedder_id: str, limit: int) -> list[CannedReply]:
        """Usable rows with no vector, or a vector from a different embedding model."""
        result = await self._session.execute(
            select(CannedReply)
            .where(
                CannedReply.enabled.is_(True),
                CannedReply.bot_eligible.is_(True),
                or_(
                    CannedReply.embedding.is_(None),
                    CannedReply.embedder_id.is_distinct_from(embedder_id),
                ),
            )
            .order_by(CannedReply.id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete(self, reply: CannedReply) -> None:
        await self._session.delete(reply)
