from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.kb_validate import PageEvidence, ValidationResult, validate_snapshot_with_pages
from app.services.kb_validate import validate_snapshot as run_validation


async def begin_snapshot(session: AsyncSession, source_id: UUID) -> UUID:
    source = await session.get(KbSource, source_id)
    if source is None:
        raise ValueError("source_not_found")
    snapshot = KbSnapshot(
        site_id=source.site_id,
        source_id=source.id,
        state="building",
        content_hash="",
        token_estimate=0,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot.id


async def validate_snapshot(
    session: AsyncSession,
    snapshot_id: UUID,
    staged_pages: dict[UUID, PageEvidence] | None = None,
) -> ValidationResult:
    if staged_pages is None:
        return await run_validation(session, snapshot_id)
    return await validate_snapshot_with_pages(session, snapshot_id, staged_pages)


async def promote(session: AsyncSession, snapshot_id: UUID) -> None:
    snapshot = await session.get(KbSnapshot, snapshot_id)
    if snapshot is None:
        raise ValueError("snapshot_not_found")
    await session.execute(
        update(KbSnapshot)
        .where(
            KbSnapshot.source_id == snapshot.source_id,
            KbSnapshot.state == "live",
        )
        .values(state="superseded")
    )
    snapshot.state = "live"
    snapshot.promoted_at = datetime.now(UTC)
    await session.flush()


async def fail(session: AsyncSession, snapshot_id: UUID, error_code: str) -> None:
    snapshot = await session.get(KbSnapshot, snapshot_id)
    if snapshot is None:
        raise ValueError("snapshot_not_found")
    snapshot.state = "failed"
    snapshot.error_code = error_code
    await session.flush()


async def mark_unchanged(session: AsyncSession, snapshot_id: UUID, content_hash: str) -> None:
    snapshot = await session.get(KbSnapshot, snapshot_id)
    if snapshot is None:
        return
    snapshot.state = "unchanged"
    snapshot.content_hash = content_hash
    await session.flush()
