"""Entries a suggested FAQ is already close to, so staff can edit one instead of adding a twin.

Kept apart from knowledge_gap_service for the same reason as knowledge_gap_answers: knowledge
search pulls in more of the app than the chat service should import just to record a miss.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canned_reply import CannedReply
from app.models.knowledge_gap import KnowledgeGap
from app.repositories.canned_reply_repo import CannedReplyRepository
from app.services.canned_bot import CANNED_COSINE_FLOOR
from app.services.kb_embedder import Embedder
from app.services.kb_hybrid import HybridKbSearch

log = structlog.get_logger("knowledge_gap")

# Same floor the bot uses to trust a canned match. Untuned for knowledge pages: if staff are
# shown too many or too few "already close" entries, this is the one number to move.
SIMILAR_FLOOR = CANNED_COSINE_FLOOR


@dataclass(frozen=True)
class ClosestCanned:
    reply: CannedReply
    similarity: float


@dataclass(frozen=True)
class ClosestKnowledge:
    title: str
    heading: str
    url: str
    similarity: float


@dataclass(frozen=True)
class Closest:
    canned: ClosestCanned | None
    knowledge: ClosestKnowledge | None


async def closest_entries(session: AsyncSession, embedder: Embedder, gap: KnowledgeGap) -> Closest:
    vector = await _gap_vector(embedder, gap)
    if vector is None:
        return Closest(None, None)
    return Closest(
        canned=await _closest_canned(session, embedder, gap, vector),
        knowledge=await _closest_knowledge(session, gap, vector),
    )


async def _gap_vector(embedder: Embedder, gap: KnowledgeGap) -> list[float] | None:
    if gap.embedding is not None and gap.embedder_id == embedder.embedder_id:
        return list(gap.embedding)
    try:
        return await embedder.embed_query(gap.question)
    except Exception:
        log.info("knowledge_gap_embed_failed")
        return None


async def _closest_canned(
    session: AsyncSession, embedder: Embedder, gap: KnowledgeGap, vector: list[float]
) -> ClosestCanned | None:
    found = await CannedReplyRepository(session).closest_to(
        gap.site_id, embedder.embedder_id, vector
    )
    if found is None or found[1] < SIMILAR_FLOOR:
        return None
    return ClosestCanned(reply=found[0], similarity=found[1])


async def _closest_knowledge(
    session: AsyncSession, gap: KnowledgeGap, vector: list[float]
) -> ClosestKnowledge | None:
    hits = await HybridKbSearch(session).search(gap.site_id, gap.question, vector)
    scored = [hit for hit in hits if hit.cosine is not None and hit.cosine >= SIMILAR_FLOOR]
    if not scored:
        return None
    best = max(scored, key=lambda hit: hit.cosine or 0.0)
    return ClosestKnowledge(
        title=best.title, heading=best.heading, url=best.url, similarity=best.cosine or 0.0
    )
