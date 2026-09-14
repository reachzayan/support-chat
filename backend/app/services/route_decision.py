from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource


async def live_snapshots_for_site(session: AsyncSession, site_id: UUID) -> list[KbSnapshot]:
    result = await session.execute(
        select(KbSnapshot)
        .join(KbSource, KbSource.id == KbSnapshot.source_id)
        .where(
            KbSnapshot.site_id == site_id,
            KbSnapshot.state == "live",
            KbSource.enabled.is_(True),
        )
        .order_by(KbSnapshot.promoted_at.desc().nullslast(), KbSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


async def site_token_estimate(session: AsyncSession, site_id: UUID) -> int:
    result = await session.execute(
        select(func.coalesce(func.sum(KbSnapshot.token_estimate), 0))
        .join(KbSource, KbSource.id == KbSnapshot.source_id)
        .where(
            KbSnapshot.site_id == site_id,
            KbSnapshot.state == "live",
            KbSource.enabled.is_(True),
        )
    )
    return int(result.scalar_one())
