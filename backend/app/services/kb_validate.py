from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_smoke_assertion import KbSmokeAssertion
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.kb_extract.text import answer_digest, visible_copy
from app.settings import get_settings

log = structlog.get_logger("kb_validate")

KINDS = {"faq", "section", "table", "definition", "prose", "refusal", "fact"}
NUMERIC_RE = re.compile(
    r"\d{1,3}(?:[\-\u2013]\d{1,3})?\s*(?:hours?|days?|minutes?|business days?)|\$\d+|\d+%",
    re.IGNORECASE,
)
TRUNCATION_SUFFIXES = ("…", "[…]", "...")


@dataclass(frozen=True)
class DroppedPage:
    page_id: UUID
    reason: str


@dataclass(frozen=True)
class ValidationResult:
    failed_rules: list[str]
    dropped: list[DroppedPage] = field(default_factory=list)


@dataclass(frozen=True)
class PageEvidence:
    id: UUID
    url: str
    raw_html: str | None
    markdown: str | None


async def validate_snapshot(session: AsyncSession, snapshot_id: UUID) -> ValidationResult:
    return await validate_snapshot_with_pages(session, snapshot_id)


async def validate_snapshot_with_pages(
    session: AsyncSession,
    snapshot_id: UUID,
    staged_pages: dict[UUID, PageEvidence] | None = None,
) -> ValidationResult:
    snapshot = await session.get(KbSnapshot, snapshot_id)
    if snapshot is None:
        return ValidationResult(failed_rules=["schema"])
    source = await session.get(KbSource, snapshot.source_id)
    chunks = list(
        (
            await session.scalars(
                select(KbChunk)
                .where(KbChunk.snapshot_id == snapshot_id)
                .order_by(KbChunk.page_id, KbChunk.ordinal)
            )
        ).all()
    )
    pages = list(
        (await session.scalars(select(KbPage).where(KbPage.source_id == snapshot.source_id))).all()
    )
    snapshot_pages = _pages_for_snapshot(pages, chunks, staged_pages or {})
    if any(chunk.site_id != snapshot.site_id for chunk in chunks):
        failed = ["tenant_isolation"]
        await _apply_snapshot_validation(session, snapshot, source, snapshot_id, failed)
        return ValidationResult(failed_rules=failed)
    live_hashes = await _live_answer_hashes(session, snapshot)
    drop_ids, drop_reasons = _drop_faulty_units(snapshot, chunks, snapshot_pages, live_hashes)
    if drop_ids:
        await session.execute(delete(KbChunk).where(KbChunk.id.in_(drop_ids)))
        await session.flush()
    remaining = [chunk for chunk in chunks if chunk.id not in drop_ids]
    enabled = [chunk for chunk in remaining if chunk.enabled]
    remaining_pages = {chunk.page_id for chunk in remaining}
    dropped = [
        DroppedPage(page_id, reason)
        for page_id, reason in drop_reasons.items()
        if page_id not in remaining_pages
    ]
    failed: list[str] = []
    if chunks and not remaining:
        failed = list(dict.fromkeys(drop_reasons.values()))
    elif chunks and not enabled:
        failed = list(dict.fromkeys(drop_reasons.values())) or ["numeric_fact_preservation"]
    elif source is not None and await _smoke_fail(session, source.id, enabled):
        failed = ["smoke_assertions"]
    await _apply_snapshot_validation(session, snapshot, source, snapshot_id, failed)
    return ValidationResult(failed_rules=failed, dropped=dropped)


def _drop_faulty_units(
    snapshot: KbSnapshot,
    chunks: list[KbChunk],
    pages: list[PageEvidence],
    live_hashes: set[str] | None = None,
) -> tuple[set[UUID], dict[UUID, str]]:
    drop_ids: set[UUID] = set()
    drop_reasons: dict[UUID, str] = {}

    def drop(chunk: KbChunk, reason: str) -> None:
        drop_ids.add(chunk.id)
        drop_reasons.setdefault(chunk.page_id, reason)

    for chunk in chunks:
        reason = _chunk_quality_reason(snapshot, chunk)
        if reason is not None:
            drop(chunk, reason)
    kept = [chunk for chunk in chunks if chunk.id not in drop_ids]
    by_page: dict[UUID, list[KbChunk]] = defaultdict(list)
    for chunk in kept:
        by_page[chunk.page_id].append(chunk)
    for page in pages:
        _apply_numeric_checks(snapshot, page, by_page.get(page.id, []), drop_reasons)
    kept = [chunk for chunk in chunks if chunk.id not in drop_ids]
    for chunk_id in _duplicate_chunk_ids(kept, pages, live_hashes or set()):
        chunk = next(item for item in kept if item.id == chunk_id)
        drop(chunk, "dedupe")
    return drop_ids, drop_reasons


def _apply_numeric_checks(
    snapshot: KbSnapshot,
    page: PageEvidence,
    page_chunks: list[KbChunk],
    drop_reasons: dict[UUID, str],
) -> None:
    source = _page_numeric_source(page)
    remaining: list[KbChunk] = []
    for chunk in page_chunks:
        if _chunk_invents_numbers(source, chunk):
            chunk.enabled = False
            if not chunk.review_note:
                chunk.review_note = "unsupported_numeric_literal"
            drop_reasons.setdefault(chunk.page_id, "numeric_fact_preservation")
            continue
        remaining.append(chunk)
    if remaining and _numeric_fail(source, remaining):
        log.info(
            "kb_validate_numeric_warning",
            snapshot_id=str(snapshot.id),
            page_id=str(page.id),
        )


def _chunk_quality_reason(snapshot: KbSnapshot, chunk: KbChunk) -> str | None:
    if not chunk.answer_verbatim or chunk.kind not in KINDS:
        return "schema"
    if chunk.site_id != snapshot.site_id:
        return "tenant_isolation"
    limit = get_settings().max_answer_chars
    answer = chunk.answer_verbatim
    if len(answer) >= limit or (
        not chunk.context_prefix and any(answer.endswith(marker) for marker in TRUNCATION_SUFFIXES)
    ):
        return "no_truncation"
    settings = get_settings()
    if len(chunk.body) > settings.chunk_target_chars or len(answer) > settings.max_answer_chars:
        return "size_cap"
    return None


async def _apply_snapshot_validation(
    session: AsyncSession,
    snapshot: KbSnapshot,
    source: KbSource | None,
    snapshot_id: UUID,
    failed: list[str],
) -> None:
    if failed:
        snapshot.state = "failed"
        snapshot.error_code = "validation"
        snapshot.validation_errors = failed
        for rule_id in failed:
            log.info(
                "kb_validate_fail",
                rule_id=rule_id,
                snapshot_id=str(snapshot_id),
            )
        if source is not None:
            source.status = "failed"
            source.error_code = "validation"
    else:
        snapshot.state = "validated"
        snapshot.validation_errors = []
    await session.flush()


def _pages_for_snapshot(
    pages: list[KbPage],
    chunks: list[KbChunk],
    staged_pages: dict[UUID, PageEvidence],
) -> list[PageEvidence]:
    page_ids = {chunk.page_id for chunk in chunks}
    return [
        staged_pages.get(
            page.id,
            PageEvidence(
                id=page.id,
                url=page.url,
                raw_html=page.raw_html,
                markdown=page.markdown,
            ),
        )
        for page in pages
        if page.id in page_ids
    ]


def _page_numeric_source(page: PageEvidence) -> str:
    return "\n".join(filter(None, [page.markdown, visible_copy(page.raw_html or "")]))


def _fold_numeric(text: str) -> str:
    return (text or "").replace("\u2013", "-").replace("\u2014", "-")


def _chunk_invents_numbers(page_source: str, chunk: KbChunk) -> bool:
    folded_page = _fold_numeric(page_source)
    folded_answer = _fold_numeric(chunk.answer_verbatim or "")
    return any(match.group(0) not in folded_page for match in NUMERIC_RE.finditer(folded_answer))


def _numeric_fail(raw_html: str, chunks: list[KbChunk]) -> bool:
    answers = _fold_numeric("\n".join(chunk.answer_verbatim for chunk in chunks))
    for match in NUMERIC_RE.finditer(_fold_numeric(raw_html)):
        if match.group(0) not in answers:
            return True
    return False


def _duplicate_chunk_ids(
    chunks: list[KbChunk],
    pages: list[PageEvidence] | None = None,
    live_hashes: set[str] | None = None,
) -> list[UUID]:
    urls = {page.id: page.url for page in pages or []}
    extras: list[UUID] = []
    seen: dict[str, KbChunk] = {}
    origins: dict[str, set[str]] = defaultdict(set)
    live = set(live_hashes or [])
    for chunk in sorted(chunks, key=lambda item: _canonical_rank(item, urls)):
        digest = answer_digest(chunk.answer_verbatim or "")
        page_url = urls.get(chunk.page_id, "")
        if page_url:
            origins[digest].add(page_url)
        if digest in live or digest in seen:
            extras.append(chunk.id)
            continue
        seen[digest] = chunk
    extra_ids = set(extras)
    for digest, winner in seen.items():
        if winner.id in extra_ids:
            continue
        unique = sorted(url for url in origins[digest] if url)
        winner.origin_urls = unique if len(unique) >= 2 else []
    return extras


def _canonical_rank(chunk: KbChunk, urls: dict[UUID, str]) -> tuple:
    path = urlparse(urls.get(chunk.page_id, "")).path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    home = 0 if path == "/" else 1
    return (home, path.count("/"), len(path), path, chunk.ordinal, str(chunk.id))


async def _live_answer_hashes(session: AsyncSession, snapshot: KbSnapshot) -> set[str]:
    rows = (
        await session.scalars(
            select(KbChunk.answer_verbatim)
            .join(KbSnapshot, KbChunk.snapshot_id == KbSnapshot.id)
            .where(
                KbSnapshot.site_id == snapshot.site_id,
                KbSnapshot.state == "live",
                KbSnapshot.source_id != snapshot.source_id,
                KbChunk.enabled.is_(True),
            )
        )
    ).all()
    return {answer_digest(text) for text in rows if text}


async def _smoke_fail(session: AsyncSession, source_id: UUID, chunks: list[KbChunk]) -> bool:
    rows = list(
        (
            await session.scalars(
                select(KbSmokeAssertion).where(KbSmokeAssertion.source_id == source_id)
            )
        ).all()
    )
    if not rows:
        return False
    combined = "\n".join(chunk.answer_verbatim for chunk in chunks)
    for row in rows:
        if any(token not in combined for token in row.must_include):
            return True
        if any(token and token in combined for token in row.must_exclude):
            return True
    return False
