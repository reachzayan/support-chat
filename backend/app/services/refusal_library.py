"""Lookup curated refusal evidence units by sensitive category."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.safety_markers import SensitiveCategory
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot

REFUSAL_BODIES: dict[SensitiveCategory, str] = {
    SensitiveCategory.SSN: (
        "Please do not share Social Security numbers or other screening identifiers."
    ),
    SensitiveCategory.DL: "Please don't share driver's licence numbers here.",
    SensitiveCategory.PLATE: "Please don't share plate numbers here.",
    SensitiveCategory.DOB: "Please don't share dates of birth here.",
    SensitiveCategory.MRN: "Please don't share medical record or specimen identifiers here.",
    SensitiveCategory.SPECIMEN: "Please don't share medical record or specimen identifiers here.",
    SensitiveCategory.INDIVIDUAL_RESULT: (
        "I can't discuss an individual's screening result in chat."
    ),
    SensitiveCategory.MEDICAL_DETAIL: "Medical details aren't safe to share in chat.",
    SensitiveCategory.LEGAL_CASE: "I can't give legal advice or interpret a case.",
}

REFUSAL_SOURCE_URL = "urn:supportchat:refusals"
REFUSAL_PAGE_URL = "urn:supportchat:refusals#policy"


@dataclass(frozen=True)
class RefusalHit:
    body: str
    chunk_id: UUID | None = None
    snapshot_id: UUID | None = None
    source_title: str = "company policy"


async def lookup_refusal(
    session: AsyncSession,
    site_id: UUID,
    category: SensitiveCategory,
) -> RefusalHit | None:
    if category is SensitiveCategory.NONE:
        return None
    result = await session.execute(
        select(KbChunk, KbPage)
        .join(KbPage, KbPage.id == KbChunk.page_id)
        .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
        .where(
            KbChunk.site_id == site_id,
            KbChunk.kind == "refusal",
            KbChunk.topic == category.value,
            KbChunk.approved.is_(True),
            KbChunk.enabled.is_(True),
            KbPage.enabled.is_(True),
            KbSnapshot.state == "live",
        )
        .order_by(KbChunk.ordinal, KbChunk.id)
        .limit(1)
    )
    row = result.one_or_none()
    if row is None:
        body = REFUSAL_BODIES.get(category)
        if body is None:
            return None
        return RefusalHit(body=body)
    chunk, _page = row
    return RefusalHit(
        body=chunk.answer_verbatim,
        chunk_id=chunk.id,
        snapshot_id=chunk.snapshot_id,
        source_title="company policy",
    )


def fallback_refusal_body(category: SensitiveCategory) -> str | None:
    return REFUSAL_BODIES.get(category)
