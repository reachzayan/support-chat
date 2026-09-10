from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.kb_extract.types import EvidenceUnit
from app.services.kb_validate import ValidationResult
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


async def append_unit(session: AsyncSession, snapshot_id: UUID, unit: EvidenceUnit) -> None:
    from app.models.kb_chunk import KbChunk
    from app.models.kb_page import KbPage
    from app.services.kb_chunk import pack_chunks
    from app.settings import get_settings

    snapshot = await session.get(KbSnapshot, snapshot_id)
    if snapshot is None:
        raise ValueError("snapshot_not_found")
    page = await session.scalar(
        select(KbPage).where(KbPage.source_id == snapshot.source_id).order_by(KbPage.fetched_at)
    )
    if page is None:
        raise ValueError("page_not_found")
    settings = get_settings()
    pieces = pack_chunks(unit, settings.chunk_target_chars, settings.chunk_overlap_chars)
    existing = await session.scalar(
        select(KbChunk.ordinal)
        .where(KbChunk.snapshot_id == snapshot_id, KbChunk.page_id == page.id)
        .order_by(KbChunk.ordinal.desc())
    )
    start = 0 if existing is None else existing + 1
    for offset, piece in enumerate(pieces):
        session.add(
            KbChunk(
                page_id=page.id,
                site_id=snapshot.site_id,
                snapshot_id=snapshot.id,
                ordinal=start + offset,
                kind=piece.kind,
                heading=piece.heading,
                canonical_question=piece.canonical_question,
                answer_verbatim=piece.answer_verbatim,
                aliases=list(piece.aliases),
                display_locator=piece.display_locator,
                body=piece.body,
                enabled=True,
            )
        )
    await session.flush()


async def validate_snapshot(session: AsyncSession, snapshot_id: UUID) -> ValidationResult:
    return await run_validation(session, snapshot_id)


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
