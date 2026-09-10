from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.kb_tokens import GENERIC_NOISE, WEAK_OVERLAP, is_overview_query, tokenize
from app.settings import get_settings

log = structlog.get_logger("faq_fastpath")

_PUNCT_RE = re.compile(r"[^\w\s?]", re.UNICODE)
_CTA_SNIPPETS = (
    "talk to a specialist",
    "get in touch",
    "jump into the portal",
)


def is_marketing_cta(text: str) -> bool:
    lowered = (text or "").casefold()
    return any(snippet in lowered for snippet in _CTA_SNIPPETS)


@dataclass(frozen=True)
class FastAnswer:
    unit_id: UUID
    answer_verbatim: str
    canonical_question: str | None
    page_url: str
    display_locator: str | None
    snapshot_id: UUID
    source_title: str
    score: float


def normalize_fast_query(value: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.casefold()
    normalized = _PUNCT_RE.sub(" ", normalized)
    normalized = " ".join(normalized.split())
    if len(normalized) < 3:
        return None
    return normalized


async def try_fast_answer(
    session: AsyncSession,
    site_id: UUID,
    snapshot_ids: list[UUID],
    normalized_query: str,
) -> FastAnswer | None:
    started = time.perf_counter()
    if not snapshot_ids or not normalized_query:
        return None
    settings = get_settings()
    ts = func.websearch_to_tsquery("english", normalized_query)
    rank = func.ts_rank_cd(KbChunk.search_document, ts)
    result = await session.execute(
        select(
            KbChunk.id,
            KbChunk.answer_verbatim,
            KbChunk.canonical_question,
            KbChunk.heading,
            KbChunk.snapshot_id,
            KbChunk.display_locator,
            KbChunk.requires_human,
            KbChunk.legal_sensitive,
            KbPage.url,
            KbPage.title,
            rank.label("score"),
        )
        .join(KbPage, KbPage.id == KbChunk.page_id)
        .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
        .join(KbSource, KbSource.id == KbPage.source_id)
        .where(
            KbChunk.site_id == site_id,
            KbChunk.snapshot_id.in_(snapshot_ids),
            KbChunk.kind != "refusal",
            KbChunk.approved.is_(True),
            KbChunk.enabled.is_(True),
            KbPage.enabled.is_(True),
            KbSnapshot.state == "live",
            KbSource.enabled.is_(True),
            KbChunk.search_document.op("@@")(ts),
        )
        .order_by(rank.desc(), KbChunk.id)
        .limit(3)
    )
    rows = [row for row in result.all() if not is_marketing_cta(row.answer_verbatim or "")]
    elapsed_ms = (time.perf_counter() - started) * 1000
    if not rows:
        log.info("faq_fastpath_miss", elapsed_ms=round(elapsed_ms, 2), reason="no_rows")
        return None
    if is_overview_query(normalized_query):
        log.info("faq_fastpath_miss", elapsed_ms=round(elapsed_ms, 2), reason="overview_query")
        return None
    top = rows[0]
    query_tokens = set(tokenize(normalized_query)) - GENERIC_NOISE
    faq_tokens = (
        set(
            tokenize(
                " ".join(
                    part
                    for part in (top.canonical_question, top.heading, top.answer_verbatim)
                    if part
                )
            )
        )
        - GENERIC_NOISE
    )
    overlap = query_tokens & faq_tokens
    if not overlap or (overlap <= WEAK_OVERLAP and len(overlap) == 1):
        log.info(
            "faq_fastpath_miss",
            elapsed_ms=round(elapsed_ms, 2),
            reason="no_content_overlap",
        )
        return None
    top_score = float(top.score or 0.0)
    second_score = float(rows[1].score or 0.0) if len(rows) > 1 else 0.0
    if top_score < settings.fast_path_min_score:
        log.info(
            "faq_fastpath_miss",
            elapsed_ms=round(elapsed_ms, 2),
            reason="min_score",
            top_score=top_score,
        )
        return None
    if second_score > 0 and top_score < settings.fast_path_margin_ratio * second_score:
        log.info(
            "faq_fastpath_miss",
            elapsed_ms=round(elapsed_ms, 2),
            reason="margin",
            top_score=top_score,
            second_score=second_score,
        )
        return None
    if top.requires_human or top.legal_sensitive:
        log.info(
            "faq_fastpath_miss",
            elapsed_ms=round(elapsed_ms, 2),
            reason="sensitive_or_human",
        )
        return None
    answer = FastAnswer(
        unit_id=top.id,
        answer_verbatim=top.answer_verbatim,
        canonical_question=top.canonical_question,
        page_url=top.url,
        display_locator=top.display_locator,
        snapshot_id=top.snapshot_id,
        source_title=top.title or top.canonical_question or "Source",
        score=top_score,
    )
    log.info(
        "faq_fastpath_hit",
        elapsed_ms=round(elapsed_ms, 2),
        unit_id=str(answer.unit_id),
        top_score=top_score,
    )
    return answer
