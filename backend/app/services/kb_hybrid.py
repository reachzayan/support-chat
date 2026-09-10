import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session_maker
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.kb_embedder import rrf_merge
from app.services.kb_tokens import is_overview_query, search_tokens

COSINE_FLOOR = 0.55
FTS_LIMIT = 8
DENSE_LIMIT = 8
PER_PAGE = 2
KEEP = 4


@dataclass(frozen=True)
class ChunkHit:
    id: UUID
    page_id: UUID
    site_id: UUID
    heading: str
    body: str
    url: str
    title: str
    rrf: float
    cosine: float | None
    answer_verbatim: str = ""
    display_locator: str | None = None
    snapshot_id: UUID | None = None
    canonical_question: str | None = None
    legal_sensitive: bool = False


class HybridKbSearch:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self, site_id: UUID, visitor_text: str, query_vector: list[float] | None = None
    ) -> list[ChunkHit]:
        fts_ids, dense_ids, cosine_by_id = await self._retrieve_arms(
            site_id, visitor_text, query_vector
        )
        ranked = rrf_merge(fts_ids, dense_ids)
        if not ranked:
            if is_overview_query(visitor_text):
                return await self._overview(site_id)
            return []
        hits = await self._load(site_id, [chunk_id for chunk_id, _score in ranked])
        diversified = self._diversify(ranked, hits, fts_ids, cosine_by_id)
        if diversified:
            return diversified
        if is_overview_query(visitor_text):
            return await self._overview(site_id)
        return []

    async def _retrieve_arms(
        self,
        site_id: UUID,
        visitor_text: str,
        query_vector: list[float] | None,
    ) -> tuple[list[UUID], list[UUID], dict[UUID, float]]:
        if query_vector is None:
            return await self._fts(site_id, visitor_text), [], {}
        async with session_maker()() as dense_session:
            fts_ids, dense_result = await asyncio.gather(
                self._fts(site_id, visitor_text),
                HybridKbSearch(dense_session)._dense(site_id, query_vector),
            )
            dense_ids, cosine_by_id = dense_result
            return fts_ids, dense_ids, cosine_by_id

    def _diversify(
        self,
        ranked: list[tuple[UUID, float]],
        hits: list[ChunkHit],
        fts_ids: list[UUID],
        cosine_by_id: dict[UUID, float],
    ) -> list[ChunkHit]:
        diversified: list[ChunkHit] = []
        per_page: dict[UUID, int] = {}
        by_id = {hit.id: hit for hit in hits}
        for chunk_id, score in ranked:
            hit = by_id.get(chunk_id)
            if hit is None:
                continue
            cosine = cosine_by_id.get(chunk_id)
            if cosine is not None and cosine < COSINE_FLOOR and chunk_id not in fts_ids:
                continue
            taken = per_page.get(hit.page_id, 0)
            if taken >= PER_PAGE:
                continue
            per_page[hit.page_id] = taken + 1
            diversified.append(
                ChunkHit(
                    id=hit.id,
                    page_id=hit.page_id,
                    site_id=hit.site_id,
                    heading=hit.heading,
                    body=hit.body,
                    url=hit.url,
                    title=hit.title,
                    rrf=score,
                    cosine=cosine,
                    answer_verbatim=hit.answer_verbatim,
                    display_locator=hit.display_locator,
                    snapshot_id=hit.snapshot_id,
                    canonical_question=hit.canonical_question,
                    legal_sensitive=hit.legal_sensitive,
                )
            )
            if len(diversified) >= KEEP:
                break
        return diversified

    async def _fts(self, site_id: UUID, visitor_text: str) -> list[UUID]:
        tokens = search_tokens(visitor_text)
        if not tokens:
            return []
        query = " OR ".join(tokens)
        ts = func.websearch_to_tsquery("english", query)
        result = await self._session.execute(
            select(KbChunk.id)
            .join(KbPage, KbPage.id == KbChunk.page_id)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .join(KbSource, KbSource.id == KbPage.source_id)
            .where(
                KbChunk.site_id == site_id,
                KbChunk.enabled.is_(True),
                KbChunk.kind != "refusal",
                KbPage.enabled.is_(True),
                KbSource.enabled.is_(True),
                KbSnapshot.state == "live",
                KbChunk.search_document.op("@@")(ts),
            )
            .order_by(func.ts_rank(KbChunk.search_document, ts).desc(), KbChunk.id)
            .limit(FTS_LIMIT)
        )
        return list(result.scalars().all())

    async def _dense(
        self, site_id: UUID, query_vector: list[float]
    ) -> tuple[list[UUID], dict[UUID, float]]:
        await self._session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
        distance = KbChunk.embedding.cosine_distance(query_vector)
        result = await self._session.execute(
            select(KbChunk.id, KbChunk.site_id, (1 - distance).label("cosine"))
            .join(KbPage, KbPage.id == KbChunk.page_id)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .join(KbSource, KbSource.id == KbPage.source_id)
            .where(
                KbChunk.site_id == site_id,
                KbChunk.enabled.is_(True),
                KbChunk.kind != "refusal",
                KbPage.enabled.is_(True),
                KbSource.enabled.is_(True),
                KbSnapshot.state == "live",
                KbChunk.embedding.is_not(None),
            )
            .order_by(distance, KbChunk.id)
            .limit(DENSE_LIMIT)
        )
        ids: list[UUID] = []
        scores: dict[UUID, float] = {}
        for chunk_id, row_site, cosine in result.all():
            if row_site != site_id:
                return [], {}
            ids.append(chunk_id)
            scores[chunk_id] = float(cosine)
        return ids, scores

    async def _overview(self, site_id: UUID) -> list[ChunkHit]:
        result = await self._session.execute(
            select(KbChunk.id)
            .join(KbPage, KbPage.id == KbChunk.page_id)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .join(KbSource, KbSource.id == KbPage.source_id)
            .where(
                KbChunk.site_id == site_id,
                KbChunk.enabled.is_(True),
                KbChunk.kind != "refusal",
                KbPage.enabled.is_(True),
                KbSource.enabled.is_(True),
                KbSnapshot.state == "live",
            )
            .order_by(KbPage.url, KbChunk.ordinal, KbChunk.id)
            .limit(KEEP)
        )
        return await self._load(site_id, list(result.scalars().all()))

    async def _load(self, site_id: UUID, chunk_ids: list[UUID]) -> list[ChunkHit]:
        if not chunk_ids:
            return []
        result = await self._session.execute(
            select(KbChunk, KbPage)
            .join(KbPage, KbPage.id == KbChunk.page_id)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .join(KbSource, KbSource.id == KbPage.source_id)
            .where(
                KbChunk.id.in_(chunk_ids),
                KbChunk.site_id == site_id,
                KbChunk.enabled.is_(True),
                KbPage.enabled.is_(True),
                KbSource.enabled.is_(True),
                KbSnapshot.state == "live",
            )
        )
        hits: list[ChunkHit] = []
        for chunk, page in result.all():
            if chunk.site_id != site_id:
                return []
            hits.append(
                ChunkHit(
                    id=chunk.id,
                    page_id=chunk.page_id,
                    site_id=chunk.site_id,
                    heading=chunk.heading,
                    body=chunk.body,
                    url=page.url,
                    title=page.title,
                    rrf=0.0,
                    cosine=None,
                    answer_verbatim=chunk.answer_verbatim,
                    display_locator=chunk.display_locator or page.display_locator,
                    snapshot_id=chunk.snapshot_id,
                    canonical_question=chunk.canonical_question,
                    legal_sensitive=bool(chunk.legal_sensitive),
                )
            )
        return hits
