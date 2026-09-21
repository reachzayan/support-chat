"""Validate and publish a staged snapshot while retaining valid live pages."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.kb_ingest_chunks import _copy_live_chunks
from app.services.kb_ingest_state import _record_job_event, _sync_status
from app.services.kb_snapshot import fail, mark_unchanged, validate_snapshot
from app.services.kb_validate import PageEvidence, ValidationResult


async def _fail_empty(session: AsyncSession, source: KbSource, snapshot_id: UUID) -> None:
    await _fail_ingest(session, source, snapshot_id, "empty")


async def _fail_ingest(
    session: AsyncSession, source: KbSource, snapshot_id: UUID, code: str
) -> None:
    await fail(session, snapshot_id, code)
    source.stage = source.status = "failed"
    source.error_code = source.last_error_code = code
    source.last_run_finished_at = datetime.now(UTC)
    await session.commit()


async def _mark_unchanged(
    session: AsyncSession,
    source: KbSource,
    snapshot_id: UUID,
    pending: list[dict],
    content_hash: str,
) -> None:
    await mark_unchanged(session, snapshot_id, content_hash)
    await _apply_staged_pages(session, pending)
    source.stage = "ready"
    source.status = "ready"
    source.error_code = None
    source.page_count = len(pending)
    source.last_run_finished_at = datetime.now(UTC)
    await session.commit()


async def _finish_ingest(
    session: AsyncSession,
    source: KbSource,
    snapshot_id: UUID,
    pending: list[dict],
    *,
    partial_run: bool = False,
) -> None:
    if not pending and source.pages_failed > 0:
        await _fail_ingest(session, source, snapshot_id, "page_failures")
        return
    if not pending and source.pages_embedded == 0 and source.pages_skipped_unchanged == 0:
        await _fail_empty(session, source, snapshot_id)
        return
    live = await session.scalar(
        select(KbSnapshot)
        .where(
            KbSnapshot.source_id == source.id,
            KbSnapshot.state == "live",
        )
        .order_by(KbSnapshot.created_at.desc())
    )
    if live is not None:
        await _carry_forward_failed_pages(session, source, snapshot_id, live.id, pending)
        if partial_run:
            await _carry_forward_unrequested_pages(session, live.id, pending)
    content_hash = _content_hash(pending)
    if (
        live is not None
        and live.content_hash == content_hash
        and source.pages_failed == 0
        and all(item.get("copy_from_live") for item in pending)
    ):
        await _mark_unchanged(session, source, snapshot_id, pending, content_hash)
        return
    if live is not None:
        await _copy_pending_live_chunks(session, source, live.id, snapshot_id, pending)
    await _stage_snapshot(session, snapshot_id, pending, content_hash)
    source.stage = "validating"
    _sync_status(source)
    staged_pages = {
        item["page_id"]: PageEvidence(
            id=item["page_id"],
            url=item["fetch_url"],
            raw_html=item.get("raw_html"),
            markdown=item.get("markdown"),
        )
        for item in pending
    }
    result = await validate_snapshot(session, snapshot_id, staged_pages)
    await _publish_validated_snapshot(session, source, snapshot_id, pending, result)


async def _publish_validated_snapshot(
    session: AsyncSession,
    source: KbSource,
    snapshot_id: UUID,
    pending: list[dict],
    result: ValidationResult,
) -> None:
    # Show precisely the published evidence, including per-chunk validation drops.
    retained = list(
        (
            await session.scalars(
                select(KbChunk)
                .where(KbChunk.snapshot_id == snapshot_id)
                .order_by(KbChunk.page_id, KbChunk.ordinal)
            )
        ).all()
    )
    for item in pending:
        if not item.get("copy_from_live"):
            item["content_text"] = "\n\n".join(
                chunk.body if item.get("structured") else chunk.answer_verbatim
                for chunk in retained
                if chunk.page_id == item["page_id"] and chunk.enabled
            )
    dropped_reasons = {item.page_id: item.reason for item in result.dropped}
    for item in pending:
        reason = dropped_reasons.get(item["page_id"])
        if reason:
            item["dropped"] = True
            item["drop_reason"] = reason
    await _record_validation_progress(session, snapshot_id, pending)
    if result.failed_rules:
        if not any(item.get("dropped") for item in pending):
            for item in pending:
                if not item.get("copy_from_live"):
                    item["dropped"] = True
                    item["drop_reason"] = result.failed_rules[0]
        await _apply_staged_pages(session, pending)
        source.stage = "failed"
        source.status = "failed"
        source.last_run_finished_at = datetime.now(UTC)
        await session.commit()
        return
    from app.services.kb_snapshot import promote

    await promote(session, snapshot_id)
    await _apply_staged_pages(session, pending)
    source.stage = "ready"
    source.status = "ready"
    source.error_code = None
    source.page_count = len({item["page_id"] for item in pending})
    source.last_run_finished_at = datetime.now(UTC)
    await session.commit()
    from app.services.full_context import clear_units_cache

    clear_units_cache()


async def _copy_pending_live_chunks(
    session: AsyncSession,
    source: KbSource,
    live_id: UUID,
    snapshot_id: UUID,
    pending: list[dict],
) -> None:
    for item in pending:
        if not item.get("copy_from_live"):
            continue
        page = await session.get(KbPage, item["page_id"])
        if page is None:
            continue
        copied, copied_tokens = await _copy_live_chunks(session, page, live_id, snapshot_id)
        if copied:
            item["token_estimate"] = copied_tokens
            if not item.get("preserve_failure") and not item.get("preserve_page_state"):
                source.pages_embedded += 1


async def _stage_snapshot(
    session: AsyncSession, snapshot_id: UUID, pending: list[dict], content_hash: str
) -> None:
    snapshot = await session.get(KbSnapshot, snapshot_id)
    if snapshot is None:
        return
    snapshot.content_hash = content_hash
    snapshot.token_estimate = sum(item.get("token_estimate", 0) for item in pending)


async def _record_validation_progress(
    session: AsyncSession, snapshot_id: UUID, pending: list[dict]
) -> None:
    for item in pending:
        if not item.get("dropped"):
            continue
        job = await session.scalar(
            select(KbPageJob).where(
                KbPageJob.page_id == item["page_id"],
                KbPageJob.snapshot_id == snapshot_id,
            )
        )
        if job is None:
            continue
        reason = str(item.get("drop_reason") or "validation")
        _record_job_event(job, "persist", "done", error_code=reason)


async def _apply_staged_pages(session: AsyncSession, pending: list[dict]) -> None:
    now = datetime.now(UTC)
    for item in pending:
        page = await session.get(KbPage, item["page_id"])
        if page is None:
            continue
        if item.get("preserve_failure") or item.get("preserve_page_state"):
            continue
        if item.get("dropped") and not item.get("copy_from_live"):
            reason = str(item.get("drop_reason") or "validation")
            page.markdown = item.get("markdown")
            if page.last_success_at is None:
                page.raw_html = item.get("raw_html")
                page.http_status = item.get("http_status", 200)
                page.content_sha256 = item["digest"]
                page.title = item["title"]
                page.content_text = item["content_text"]
                page.display_locator = item.get("display_locator")
            page.processing_status = "failed"
            page.skip_reason = reason
            page.failure_reason = reason
            continue
        page.raw_html = item.get("raw_html")
        page.markdown = item.get("markdown")
        page.http_status = item.get("http_status", 200)
        page.content_sha256 = item["digest"]
        if not item.get("copy_from_live"):
            page.title = item["title"]
            page.content_text = item["content_text"]
            page.display_locator = item.get("display_locator")
        page.processing_status = "unchanged" if item.get("copy_from_live") else "ready"
        page.skip_reason = None
        page.failure_reason = None
        page.last_success_at = now


async def _carry_forward_failed_pages(
    session: AsyncSession,
    source: KbSource,
    snapshot_id: UUID,
    live_id: UUID,
    pending: list[dict],
) -> None:
    pending_ids = {item["page_id"] for item in pending}
    failed_page_ids = set(
        (
            await session.scalars(
                select(KbPageJob.page_id).where(
                    KbPageJob.source_id == source.id,
                    KbPageJob.snapshot_id == snapshot_id,
                    KbPageJob.state == "dead_letter",
                )
            )
        ).all()
    )
    for page_id in failed_page_ids - pending_ids:
        has_live_chunks = await session.scalar(
            select(KbChunk.id).where(
                KbChunk.page_id == page_id,
                KbChunk.snapshot_id == live_id,
            )
        )
        page = await session.get(KbPage, page_id)
        if page is None or has_live_chunks is None:
            continue
        pending.append(
            {
                "fetch_url": page.url,
                "digest": page.content_sha256,
                "token_estimate": 0,
                "copy_from_live": True,
                "preserve_failure": True,
                "page_id": page.id,
                "raw_html": page.raw_html,
                "markdown": page.markdown,
                "http_status": page.http_status,
            }
        )


async def _carry_forward_unrequested_pages(
    session: AsyncSession, live_id: UUID, pending: list[dict]
) -> None:
    pending_ids = {item["page_id"] for item in pending}
    live_page_ids = set(
        (
            await session.scalars(
                select(KbChunk.page_id).where(KbChunk.snapshot_id == live_id).distinct()
            )
        ).all()
    )
    for page_id in live_page_ids - pending_ids:
        page = await session.get(KbPage, page_id)
        if page is None:
            continue
        pending.append(
            {
                "fetch_url": page.url,
                "digest": page.content_sha256,
                "token_estimate": 0,
                "copy_from_live": True,
                "preserve_page_state": True,
                "page_id": page.id,
                "raw_html": page.raw_html,
                "markdown": page.markdown,
                "http_status": page.http_status,
            }
        )


def _content_hash(pending: list[dict]) -> str:
    pairs = sorted((item["fetch_url"], item["digest"]) for item in pending)
    blob = "\n".join(f"{url}\t{digest}" for url, digest in pairs)
    return hashlib.sha256(blob.encode()).hexdigest()
