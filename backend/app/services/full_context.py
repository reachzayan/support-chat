from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.message import Message
from app.services.faq_fastpath import is_marketing_cta, normalize_fast_query
from app.services.kb_tokens import GENERIC_NOISE, WEAK_OVERLAP, is_overview_query, tokenize
from app.settings import get_settings

_UNITS_CACHE: dict[tuple[UUID, ...], list[EvidenceDoc]] = {}


@dataclass(frozen=True)
class EvidenceDoc:
    id: UUID
    snapshot_id: UUID
    page_id: UUID
    heading: str
    canonical_question: str | None
    answer_verbatim: str
    url: str
    title: str
    display_locator: str | None
    legal_sensitive: bool
    ordinal: int
    aliases: tuple[str, ...] = ()
    topic_label: str | None = None
    risk_class: str = "general"
    answer_mode: str = "paraphrase_allowed"


def redact_window_body(body: str) -> str:
    from app.services.pii_redactor import redact_for_model

    return redact_for_model((body or "").strip())


def conversation_window_messages(rows: list[Message], *, limit: int | None = None) -> list[dict]:
    settings = get_settings()
    size = limit if limit is not None else settings.conversation_window_size
    selected = [row for row in rows if row.role in {"visitor", "bot"}][-size:]
    messages: list[dict] = []
    for row in selected:
        role = "user" if row.role == "visitor" else "assistant"
        text = redact_window_body(row.body)
        if not text:
            continue
        messages.append({"role": role, "content": text})
    return messages


def prior_provider_messages(rows: list[Message], visitor_text: str) -> list[dict]:
    messages = conversation_window_messages(rows)
    current = redact_window_body(visitor_text)
    if messages and messages[-1]["role"] == "user" and messages[-1]["content"] == current:
        return messages[:-1]
    return messages


async def load_live_units(session: AsyncSession, snapshot_ids: list[UUID]) -> list[EvidenceDoc]:
    if not snapshot_ids:
        return []
    cache_key = tuple(sorted(snapshot_ids))
    cached = _UNITS_CACHE.get(cache_key)
    if cached is not None:
        return list(cached)
    result = await session.execute(
        select(KbChunk, KbPage)
        .join(KbPage, KbPage.id == KbChunk.page_id)
        .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
        .join(KbSource, KbSource.id == KbPage.source_id)
        .where(
            KbChunk.snapshot_id.in_(snapshot_ids),
            KbChunk.enabled.is_(True),
            KbChunk.kind != "refusal",
            KbPage.enabled.is_(True),
            KbSnapshot.state == "live",
            KbSource.enabled.is_(True),
        )
        .order_by(KbChunk.page_id, KbChunk.ordinal, KbChunk.id)
    )
    units: list[EvidenceDoc] = []
    for chunk, page in result.all():
        units.append(
            EvidenceDoc(
                id=chunk.id,
                snapshot_id=chunk.snapshot_id,
                page_id=chunk.page_id,
                heading=chunk.heading,
                canonical_question=chunk.canonical_question,
                answer_verbatim=chunk.answer_verbatim,
                url=page.url,
                title=page.title,
                display_locator=chunk.display_locator or page.display_locator,
                legal_sensitive=bool(chunk.legal_sensitive),
                ordinal=chunk.ordinal,
                aliases=tuple(chunk.aliases or ()),
                topic_label=chunk.topic_label,
                risk_class=chunk.risk_class,
                answer_mode=chunk.answer_mode,
            )
        )
    _UNITS_CACHE[cache_key] = list(units)
    return units


async def likeliest_unit_id(
    session: AsyncSession,
    site_id: UUID,
    snapshot_ids: list[UUID],
    visitor_text: str,
) -> UUID | None:
    normalized = normalize_fast_query(visitor_text)
    if normalized is None or not snapshot_ids:
        return None
    if is_overview_query(visitor_text):
        return None
    ts = func.websearch_to_tsquery("english", normalized)
    rank = func.ts_rank_cd(KbChunk.search_document, ts)
    result = await session.execute(
        select(KbChunk.id, rank.label("score"))
        .where(
            KbChunk.site_id == site_id,
            KbChunk.snapshot_id.in_(snapshot_ids),
            KbChunk.enabled.is_(True),
            KbChunk.search_document.op("@@")(ts),
        )
        .order_by(rank.desc(), KbChunk.id)
        .limit(2)
    )
    rows = list(result.all())
    if not rows:
        return None
    top_score = float(rows[0].score or 0.0)
    second = float(rows[1].score or 0.0) if len(rows) > 1 else 0.0
    # Laxer than fast path: accept a weak top hit for Lost-in-the-Middle reordering.
    if top_score <= 0:
        return None
    if second > 0 and top_score < 1.1 * second:
        return None
    return rows[0].id


def order_units_for_prompt(units: list[EvidenceDoc], prefer_id: UUID | None) -> list[EvidenceDoc]:
    if prefer_id is None:
        return list(units)
    preferred = [item for item in units if item.id == prefer_id]
    rest = [item for item in units if item.id != prefer_id]
    return rest + preferred


def _unit_tokens(unit: EvidenceDoc) -> set[str]:
    blob = " ".join(
        part for part in (unit.canonical_question, unit.heading, unit.answer_verbatim) if part
    )
    return set(tokenize(blob)) - GENERIC_NOISE


def units_matching_query(units: list[EvidenceDoc], visitor_text: str) -> list[EvidenceDoc]:
    query = set(tokenize(visitor_text)) - GENERIC_NOISE
    if not query:
        return []
    matched: list[EvidenceDoc] = []
    for unit in units:
        if is_marketing_cta(unit.answer_verbatim):
            continue
        overlap = query & _unit_tokens(unit)
        if not overlap:
            continue
        if overlap <= WEAK_OVERLAP and len(overlap) == 1 and not is_overview_query(visitor_text):
            continue
        matched.append(unit)
    if is_overview_query(visitor_text) and not matched:
        return list(units)
    if not matched:
        return list(units)
    return matched


def clear_units_cache() -> None:
    _UNITS_CACHE.clear()
