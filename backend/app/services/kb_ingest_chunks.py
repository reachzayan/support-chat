"""Evidence cleaning, embedding, and chunk persistence."""

from __future__ import annotations

import asyncio
import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_page_llm_extract import KbPageLlmExtract
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.kb_chunk import TextChunk, pack_chunks, split_chunks_for_embed
from app.services.kb_embedder import Embedder, count_embed_tokens
from app.services.kb_extract.types import EvidenceUnit
from app.services.kb_ingest_state import CONTENT_FINGERPRINT_VERSION, _pg_safe
from app.services.kb_llm_extract import apply_cleaner
from app.settings import get_settings


async def _copy_live_chunks(
    session: AsyncSession, page: KbPage, live_id: UUID, snapshot_id: UUID
) -> tuple[int, int]:
    rows = list(
        (
            await session.scalars(
                select(KbChunk).where(KbChunk.page_id == page.id, KbChunk.snapshot_id == live_id)
            )
        ).all()
    )
    copied = 0
    token_total = 0
    for chunk in rows:
        session.add(
            KbChunk(
                page_id=page.id,
                site_id=chunk.site_id,
                snapshot_id=snapshot_id,
                ordinal=chunk.ordinal,
                kind=chunk.kind,
                heading=chunk.heading,
                canonical_question=chunk.canonical_question,
                answer_verbatim=chunk.answer_verbatim,
                aliases=list(chunk.aliases or []),
                topic=chunk.topic,
                approved=chunk.approved,
                review_status=chunk.review_status,
                reviewed_by=chunk.reviewed_by,
                reviewed_at=chunk.reviewed_at,
                review_note=chunk.review_note,
                content_hash=chunk.content_hash,
                risk_class=chunk.risk_class,
                answer_mode=chunk.answer_mode,
                topic_label=chunk.topic_label,
                requires_human=chunk.requires_human,
                legal_sensitive=chunk.legal_sensitive,
                display_locator=chunk.display_locator,
                body=chunk.body,
                context_prefix=chunk.context_prefix,
                embedding=chunk.embedding,
                enabled=chunk.enabled,
            )
        )
        copied += 1
        token_total += count_embed_tokens(chunk.body)
    if copied:
        await session.flush()
    return copied, token_total


async def _clean_units(
    session: AsyncSession,
    page: KbPage,
    digest: str,
    units: list[EvidenceUnit],
    llm_client,
    lock: asyncio.Lock | None = None,
    *,
    crawl_text: str | None = None,
    crawl_title: str = "",
    crawl_metadata: dict | None = None,
) -> list[EvidenceUnit]:
    if crawl_text is None:
        return apply_cleaner(units)
    version = f"{CONTENT_FINGERPRINT_VERSION}:{getattr(llm_client, 'model', 'local')}"
    gate = lock or asyncio.Lock()
    async with gate:
        cached = await session.scalar(
            select(KbPageLlmExtract).where(
                KbPageLlmExtract.page_id == page.id,
                KbPageLlmExtract.content_sha256 == digest,
                KbPageLlmExtract.prompt_version == version,
            )
        )
        if cached is not None:
            restored = _units_from_payload(cached.payload)
            if restored is not None:
                return restored
    structured = await llm_client.structure_page(page.url, crawl_title, crawl_text, crawl_metadata)
    payload = _units_payload(structured.units)
    async with gate:
        session.add(
            KbPageLlmExtract(
                page_id=page.id,
                content_sha256=digest,
                prompt_version=version,
                payload=payload,
                model=getattr(llm_client, "model", "local"),
                input_tokens=structured.input_tokens,
                output_tokens=structured.output_tokens,
                cache_read_tokens=structured.cache_read_tokens,
            )
        )
        await session.flush()
    return structured.units


def _units_payload(units: list[EvidenceUnit]) -> dict:
    return {
        "units": [
            {
                "kind": unit.kind,
                "heading": unit.heading,
                "canonical_question": unit.canonical_question,
                "answer_verbatim": unit.answer_verbatim,
                "aliases": list(unit.aliases),
                "topic": unit.topic,
                "display_locator": unit.display_locator,
                "structured_text": unit.structured_text,
                "enabled": unit.enabled,
                "review_note": unit.review_note,
            }
            for unit in units
        ]
    }


def _units_from_payload(payload: dict) -> list[EvidenceUnit] | None:
    if not isinstance(payload, dict):
        return None
    rows = payload.get("units")
    if not isinstance(rows, list):
        return None
    units: list[EvidenceUnit] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        answer = str(row.get("answer_verbatim") or "")
        heading = str(row.get("heading") or "")
        if not answer:
            continue
        kind = str(row.get("kind") or "section")
        if kind not in {"faq", "section", "table", "definition", "prose", "fact"}:
            kind = "section"
        aliases = row.get("aliases") or []
        units.append(
            EvidenceUnit(
                kind=kind,  # type: ignore[arg-type]
                heading=heading,
                canonical_question=str(row["canonical_question"])
                if row.get("canonical_question")
                else None,
                answer_verbatim=answer,
                body_for_search=f"{row.get('canonical_question') or heading}\n{row.get('structured_text') or answer}",
                display_locator=str(row["display_locator"]) if row.get("display_locator") else None,
                aliases=tuple(str(item) for item in aliases if isinstance(item, str)),
                topic=str(row["topic"]) if row.get("topic") else None,
                structured_text=str(row["structured_text"]) if row.get("structured_text") else None,
                enabled=bool(row.get("enabled", True)),
                review_note=str(row["review_note"]) if row.get("review_note") else None,
            )
        )
    return units


async def _persist_chunks(
    session: AsyncSession,
    source: KbSource,
    page: KbPage,
    snapshot_id: UUID,
    pieces: list[TextChunk],
    vectors: list[list[float]],
) -> None:
    live_rows = list(
        (
            await session.scalars(
                select(KbChunk)
                .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
                .where(KbSnapshot.source_id == source.id, KbSnapshot.state == "live")
            )
        ).all()
    )
    reviewed_by_hash = {chunk.content_hash: chunk for chunk in live_rows if chunk.content_hash}
    for ordinal, part in enumerate(pieces):
        _add_chunk_row(
            session,
            source,
            page,
            snapshot_id,
            ordinal,
            part,
            vectors[ordinal] if vectors else None,
            reviewed_by_hash,
        )
    await session.flush()


async def _prepare_chunks(
    units: list[EvidenceUnit], worker: Embedder
) -> tuple[list[TextChunk], list[list[float]], int]:
    settings = get_settings()
    pieces: list[TextChunk] = []
    for unit in units:
        pieces.extend(
            pack_chunks(
                unit,
                settings.chunk_target_chars,
                settings.chunk_overlap_chars,
            )
        )
    pieces = split_chunks_for_embed(pieces, settings.openai_embed_max_tokens)
    texts = [part.body for part in pieces]
    vectors = await worker.embed_documents(texts) if texts else []
    if texts and (len(vectors) != len(texts) or any(item is None for item in vectors)):
        raise RuntimeError("embed")
    return pieces, vectors, sum(count_embed_tokens(part.body) for part in pieces)


def _add_chunk_row(
    session: AsyncSession,
    source: KbSource,
    page: KbPage,
    snapshot_id: UUID,
    ordinal: int,
    part: TextChunk,
    vector: list[float] | None,
    reviewed_by_hash: dict[str, KbChunk],
) -> None:
    heading = _pg_safe(part.heading or "")
    canonical_question = _pg_safe(part.canonical_question or "") or None
    aliases = [_pg_safe(alias) for alias in part.aliases]
    answer_verbatim = _pg_safe(part.answer_verbatim or "")
    body = _pg_safe(part.body)
    content_hash = _chunk_content_hash(
        heading=heading,
        canonical_question=canonical_question,
        aliases=aliases,
        answer_verbatim=answer_verbatim,
        body=body,
    )
    prior = reviewed_by_hash.get(content_hash)
    session.add(
        KbChunk(
            page_id=page.id,
            site_id=source.site_id,
            snapshot_id=snapshot_id,
            ordinal=ordinal,
            kind=part.kind,
            heading=heading,
            canonical_question=canonical_question,
            answer_verbatim=answer_verbatim,
            aliases=aliases,
            topic=part.topic,
            display_locator=part.display_locator,
            body=body,
            context_prefix=part.context_prefix,
            embedding=vector,
            enabled=prior.enabled if prior is not None else part.enabled,
            review_note=prior.review_note if prior is not None else part.review_note,
            approved=True,
            review_status="approved",
            topic_label=(prior.topic_label if prior is not None else heading) or heading,
            content_hash=content_hash,
            risk_class=prior.risk_class if prior is not None else "general",
            answer_mode=prior.answer_mode if prior is not None else "paraphrase_allowed",
        )
    )


def _chunk_content_hash(
    *,
    heading: str,
    canonical_question: str | None,
    aliases: list[str],
    answer_verbatim: str,
    body: str,
) -> str:
    payload = json.dumps(
        {
            "aliases": aliases,
            "answer_verbatim": answer_verbatim,
            "body": body,
            "canonical_question": canonical_question,
            "heading": heading,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
