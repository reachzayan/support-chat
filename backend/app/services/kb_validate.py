from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_smoke_assertion import KbSmokeAssertion
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.kb_extract.jsonld import parse_faqpage
from app.services.kb_extract.text import answer_hash, tidy_text, visible_copy
from app.settings import get_settings

log = structlog.get_logger("kb_validate")

KINDS = {"faq", "section", "table", "definition", "prose", "refusal", "fact"}
NUMERIC_RE = re.compile(
    r"\d{1,3}(?:[\-\u2013]\d{1,3})?\s*(?:hours?|days?|minutes?|business days?)|\$\d+|\d+%",
    re.IGNORECASE,
)
TRUNCATION_SUFFIXES = ("…", "[…]", "...")


@dataclass(frozen=True)
class ValidationResult:
    failed_rules: list[str]


@dataclass(frozen=True)
class PageEvidence:
    id: UUID
    url: str
    raw_html: str | None
    markdown: str | None


async def _snapshot_failures(
    session: AsyncSession,
    snapshot: KbSnapshot,
    source: KbSource | None,
    chunks: list[KbChunk],
    pages: list[PageEvidence],
) -> list[str]:
    failed: list[str] = []
    if _schema_fail(snapshot, chunks):
        failed.append("schema")
    if any(chunk.site_id != snapshot.site_id for chunk in chunks):
        failed.append("tenant_isolation")
    if _truncation_fail(chunks):
        failed.append("no_truncation")
    if _numeric_fail(_numeric_source(pages), chunks):
        failed.append("numeric_fact_preservation")
    if _faq_pair_fail(pages, chunks):
        failed.append("faq_pair_preservation")
    if _dedupe_fail(chunks):
        failed.append("dedupe")
    if _size_fail(chunks):
        failed.append("size_cap")
    if source is not None and await _smoke_fail(session, source.id, chunks):
        failed.append("smoke_assertions")
    return failed


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
        (await session.scalars(select(KbChunk).where(KbChunk.snapshot_id == snapshot_id))).all()
    )
    pages = list(
        (await session.scalars(select(KbPage).where(KbPage.source_id == snapshot.source_id))).all()
    )
    snapshot_pages = _pages_for_snapshot(pages, chunks, staged_pages or {})
    failed = await _snapshot_failures(session, snapshot, source, chunks, snapshot_pages)
    await _apply_snapshot_validation(session, snapshot, source, snapshot_id, failed)
    return ValidationResult(failed_rules=failed)


def _schema_fail(snapshot: KbSnapshot, chunks: list[KbChunk]) -> bool:
    for chunk in chunks:
        if not chunk.answer_verbatim:
            return True
        if chunk.kind not in KINDS:
            return True
        if chunk.site_id != snapshot.site_id:
            return True
    return False


def _truncation_fail(chunks: list[KbChunk]) -> bool:
    limit = get_settings().max_answer_chars
    for chunk in chunks:
        answer = chunk.answer_verbatim
        if len(answer) >= limit:
            return True
        if any(answer.endswith(marker) for marker in TRUNCATION_SUFFIXES):
            return True
    return False


def _numeric_source(pages: list[PageEvidence]) -> str:
    parts: list[str] = []
    for page in pages:
        copy = (page.markdown or "").strip()
        if not copy:
            copy = visible_copy(page.raw_html or "")
        parts.append(copy)
    return "\n".join(parts)


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


def _numeric_fail(raw_html: str, chunks: list[KbChunk]) -> bool:
    answers = "\n".join(chunk.answer_verbatim for chunk in chunks)
    for match in NUMERIC_RE.finditer(raw_html):
        if match.group(0) not in answers:
            return True
    return False


def _faq_pair_fail(pages: list[PageEvidence], chunks: list[KbChunk]) -> bool:
    expected: list[tuple[UUID, str, str]] = []
    for page in pages:
        if not page.raw_html:
            continue
        expected.extend(
            (page.id, unit.canonical_question, unit.answer_verbatim)
            for unit in parse_faqpage(page.raw_html, page.url)
            if unit.canonical_question
        )
    for page_id, question, answer in expected:
        matching = sorted(
            (
                chunk
                for chunk in chunks
                if chunk.page_id == page_id and chunk.canonical_question == question
            ),
            key=lambda chunk: (chunk.ordinal, str(chunk.id)),
        )
        if not matching:
            return True
        if not _chunks_cover_answer(answer, [chunk.answer_verbatim for chunk in matching]):
            return True
    return False


def _chunks_cover_answer(answer: str, parts: list[str]) -> bool:
    if not parts:
        return False
    expected = " ".join(tidy_text(answer).split())
    intervals: list[tuple[int, int]] = []
    for raw in parts:
        part = " ".join(tidy_text(raw).split())
        if not part:
            return False
        start = 0
        found = False
        while (index := expected.find(part, start)) >= 0:
            intervals.append((index, index + len(part)))
            found = True
            start = index + 1
        if not found:
            return False
    covered = 0
    for start, end in sorted(intervals):
        if start > covered:
            break
        covered = max(covered, end)
        if covered == len(expected):
            return True
    return False


def _dedupe_fail(chunks: list[KbChunk]) -> bool:
    by_page: dict[UUID, dict[str, set[str]]] = {}
    for chunk in chunks:
        page_map = by_page.setdefault(chunk.page_id, {})
        digest = answer_hash(chunk.answer_verbatim)
        identity = chunk.canonical_question or chunk.heading
        page_map.setdefault(digest, set()).add(identity)
    return any(len(idents) > 1 for page_map in by_page.values() for idents in page_map.values())


def _size_fail(chunks: list[KbChunk]) -> bool:
    settings = get_settings()
    for chunk in chunks:
        if len(chunk.body) > settings.chunk_target_chars:
            return True
        if len(chunk.answer_verbatim) > settings.max_answer_chars:
            return True
    return False


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
