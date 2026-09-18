import asyncio
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

import structlog
from sqlalchemy import String, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.display_citations import visitor_citation_url
from app.db import session_maker
from app.llm.safety_markers import contains_injection_marker
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.bot_trace import record_trace
from app.services.faq_fastpath import is_marketing_cta
from app.services.kb_embedder import rrf_merge
from app.services.kb_tokens import is_overview_query, search_tokens, tokenize

log = structlog.get_logger("kb_hybrid")

COSINE_FLOOR = 0.35
FTS_LIMIT = 20
DENSE_LIMIT = 20
KEEP = 8
TRGM_SKIP_EMBED_FLOOR = 0.60

_TRGM_EXPR = (
    "lower("
    "coalesce(canonical_question, '') || ' ' || "
    "kb_aliases_as_text(aliases) || ' ' || "
    "coalesce(heading, '') || ' ' || "
    "coalesce(topic_label, '')"
    ")"
)


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
    aliases: tuple[str, ...] = ()
    topic_label: str | None = None
    risk_class: str = "general"
    answer_mode: str = "paraphrase_allowed"
    enabled: bool = True
    structured: bool = False


def _normalized(value: str) -> str:
    text_value = unicodedata.normalize("NFKC", value or "").casefold()
    return " ".join(text_value.split())


def _elapsed_ms(started_ns: int) -> int:
    return (time.perf_counter_ns() - started_ns) // 1_000_000


def _retrieval_text(visitor_text: str) -> str:
    if is_overview_query(visitor_text):
        return f"{visitor_text} products solutions capabilities"
    return visitor_text


def _cap_overview(hits: list[ChunkHit], keep: int = KEEP) -> list[ChunkHit]:
    kept: list[ChunkHit] = []
    seen: set[str] = set()
    for hit in hits:
        heading = _normalized(hit.heading)
        key = heading or str(hit.id)
        if key in seen:
            continue
        seen.add(key)
        kept.append(hit)
        if len(kept) >= keep:
            break
    return kept


class HybridKbSearch:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self, site_id: UUID, visitor_text: str, query_vector: list[float] | None = None
    ) -> list[ChunkHit]:
        exact = await self._exact_match(site_id, visitor_text)
        if exact is not None:
            record_trace("retrieval", mode="exact", hits=[exact])
            log.info(
                "grounded_retrieve",
                hit_ids=[str(exact.id)],
                exact_match=True,
                overview_merged=False,
                dense_used=query_vector is not None,
            )
            return [exact]

        if is_overview_query(visitor_text):
            overview = await self._overview(site_id, visitor_text)
            if overview:
                record_trace("retrieval", mode="overview", hits=overview)
                return overview

        retrieval_text = _retrieval_text(visitor_text)
        fts_scored, dense_ids, cosine_by_id = await self._retrieve_arms(
            site_id, retrieval_text, query_vector
        )
        fts_ids = [chunk_id for chunk_id, _score in fts_scored]
        ranked = rrf_merge(fts_ids, dense_ids)
        if not ranked:
            return []
        hits = await self._load(site_id, [chunk_id for chunk_id, _score in ranked])
        diversified = self._diversify(ranked, hits, fts_ids, cosine_by_id, retrieval_text)
        record_trace("retrieval", mode="hybrid", hits=diversified)
        if diversified:
            log.info(
                "grounded_retrieve",
                hit_ids=[str(hit.id) for hit in diversified],
                exact_match=False,
                overview_merged=False,
                dense_used=bool(dense_ids),
            )
            return diversified
        return []

    async def search_with_deferred_embed(
        self,
        embedder,
        site_id: UUID,
        visitor_text: str,
        stage_timings: dict[str, int] | None = None,
    ) -> list[ChunkHit]:
        timings = stage_timings if stage_timings is not None else {}
        exact = await self._exact_match(site_id, visitor_text)
        if exact is not None:
            record_trace("retrieval", mode="exact", hits=[exact])
            timings.setdefault("lexical_retrieve", 0)
            timings.setdefault("trigram_retrieve", 0)
            timings.setdefault("embed", 0)
            timings.setdefault("dense_retrieve", 0)
            log.info(
                "grounded_retrieve",
                hit_ids=[str(exact.id)],
                exact_match=True,
                overview_merged=False,
                dense_used=False,
            )
            return [exact]

        if is_overview_query(visitor_text):
            overview = await self._overview(site_id, visitor_text)
            if overview:
                record_trace("retrieval", mode="overview", hits=overview)
                timings.setdefault("embed", 0)
                timings.setdefault("dense_retrieve", 0)
                return overview

        started = time.perf_counter_ns()
        retrieval_text = _retrieval_text(visitor_text)
        async with session_maker()() as trgm_session:
            fts_scored, trgm_scored = await asyncio.gather(
                self._fts(site_id, retrieval_text),
                HybridKbSearch(trgm_session)._trigram(site_id, retrieval_text),
            )
        # Split wall time evenly across the concurrent lexical arms for observability.
        lexical_ms = _elapsed_ms(started)
        timings["lexical_retrieve"] = lexical_ms
        timings["trigram_retrieve"] = lexical_ms

        fts_ids = [chunk_id for chunk_id, _score in fts_scored]
        trgm_ids = [chunk_id for chunk_id, _score in trgm_scored]
        skip_embed = bool(
            trgm_scored
            and trgm_scored[0][1] >= TRGM_SKIP_EMBED_FLOOR
            and trgm_scored[0][0] in fts_ids[:3]
        )

        dense_ids: list[UUID] = []
        cosine_by_id: dict[UUID, float] = {}
        if skip_embed:
            timings["embed"] = 0
            timings["dense_retrieve"] = 0
        else:
            started = time.perf_counter_ns()
            query_vector: list[float] | None = None
            try:
                query_vector = await embedder.embed_query(retrieval_text)
            except Exception:
                log.info("grounded_embed_failed", site_id=str(site_id))
            timings["embed"] = _elapsed_ms(started)
            if query_vector is not None:
                started = time.perf_counter_ns()
                dense_ids, cosine_by_id = await self._dense(site_id, query_vector)
                timings["dense_retrieve"] = _elapsed_ms(started)
            else:
                timings["dense_retrieve"] = 0

        record_trace(
            "retrieval",
            fts_scores=fts_scored,
            trigram_scores=trgm_scored,
            dense_cosines=cosine_by_id,
            embed_skipped=skip_embed,
        )
        ranked = rrf_merge(fts_ids, trgm_ids, dense_ids)
        if not ranked:
            return []
        hits = await self._load(site_id, [chunk_id for chunk_id, _score in ranked])
        record_trace("retrieval", fused_ranking=ranked)
        lexical_ids = list(dict.fromkeys([*fts_ids, *trgm_ids]))
        diversified = self._diversify(ranked, hits, lexical_ids, cosine_by_id, retrieval_text)
        record_trace("retrieval", mode="hybrid", hits=diversified)
        if diversified:
            log.info(
                "grounded_retrieve",
                hit_ids=[str(hit.id) for hit in diversified],
                exact_match=False,
                overview_merged=False,
                dense_used=bool(dense_ids),
            )
            return diversified
        return []

    async def _exact_match(self, site_id: UUID, visitor_text: str) -> ChunkHit | None:
        query = _normalized(visitor_text)
        if len(query) < 3:
            return None
        result = await self._session.execute(
            select(KbChunk, KbPage, KbSource)
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
                or_(
                    func.lower(func.coalesce(KbChunk.canonical_question, "")) == query,
                    cast(KbChunk.aliases, String).ilike(f'%"{query}"%'),
                ),
            )
            .order_by(KbChunk.id)
            .limit(8)
        )
        matches: list[ChunkHit] = []
        for chunk, page, source in result.all():
            if contains_injection_marker(chunk.answer_verbatim) or contains_injection_marker(
                chunk.heading or ""
            ):
                continue
            if is_marketing_cta(chunk.answer_verbatim):
                continue
            aliases = tuple(chunk.aliases or [])
            candidates = [chunk.canonical_question or "", *aliases]
            if query not in {_normalized(item) for item in candidates if item}:
                continue
            matches.append(self._to_hit(chunk, page, source, rrf=1.0))
        if len(matches) == 1:
            return matches[0]
        return None

    async def _retrieve_arms(
        self,
        site_id: UUID,
        visitor_text: str,
        query_vector: list[float] | None,
    ) -> tuple[list[tuple[UUID, float]], list[UUID], dict[UUID, float]]:
        if query_vector is None:
            return await self._fts(site_id, visitor_text), [], {}
        async with session_maker()() as dense_session:
            fts_scored, dense_result = await asyncio.gather(
                self._fts(site_id, visitor_text),
                HybridKbSearch(dense_session)._dense(site_id, query_vector),
            )
            dense_ids, cosine_by_id = dense_result
            return fts_scored, dense_ids, cosine_by_id

    def _diversify(
        self,
        ranked: list[tuple[UUID, float]],
        hits: list[ChunkHit],
        fts_ids: list[UUID],
        cosine_by_id: dict[UUID, float],
        visitor_text: str = "",
    ) -> list[ChunkHit]:
        diversified: list[ChunkHit] = []
        by_id = {hit.id: hit for hit in hits}
        # Reward coverage of distinctive query terms, not an absolute heading
        # match. Keep heading context: a section's subject may occur only there.
        query_terms = set(tokenize(visitor_text))
        terms_by_id = {
            hit.id: set(tokenize(f"{hit.heading} {hit.answer_verbatim}")) for hit in hits
        }
        counts = Counter(term for terms in terms_by_id.values() for term in terms & query_terms)
        if len(query_terms) > 1:
            ranked = sorted(
                ranked,
                key=lambda item: (
                    -sum(
                        1 / counts[term] for term in terms_by_id.get(item[0], set()) & query_terms
                    ),
                    -item[1],
                    str(item[0]),
                ),
            )
        # Fusion and lexical heading boosts can bury the best semantic answer
        # when only the dense arm understands the wording. Reserve two slots
        # and fill the remaining budget with the hybrid ranking. Do not impose
        # a per-page quota: one product page may contain all relevant facts.
        dense_first = [
            chunk_id
            for chunk_id, cosine in sorted(
                cosine_by_id.items(), key=lambda item: (-item[1], str(item[0]))
            )
            if cosine >= COSINE_FLOOR and chunk_id in by_id
        ][:2]
        scores = dict(ranked)
        ranked = [(chunk_id, scores[chunk_id]) for chunk_id in dense_first] + [
            item for item in ranked if item[0] not in dense_first
        ]
        skipped: list[dict] = []
        for chunk_id, score in ranked:
            hit = by_id.get(chunk_id)
            if hit is None:
                continue
            cosine = cosine_by_id.get(chunk_id)
            if cosine is not None and cosine < COSINE_FLOOR and chunk_id not in fts_ids:
                skipped.append({"id": chunk_id, "reason": "below_cosine_floor"})
                continue
            if len(diversified) >= KEEP:
                skipped.append({"id": chunk_id, "reason": "document_budget"})
                continue
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
                    aliases=hit.aliases,
                    topic_label=hit.topic_label,
                    risk_class=hit.risk_class,
                    answer_mode=hit.answer_mode,
                    enabled=hit.enabled,
                    structured=hit.structured,
                )
            )
        record_trace(
            "retrieval",
            selection_ranking=ranked,
            selection_skipped=skipped,
            candidates=hits,
        )
        return diversified

    async def _fts(self, site_id: UUID, visitor_text: str) -> list[tuple[UUID, float]]:
        tokens = search_tokens(visitor_text)
        if not tokens:
            return []
        query = " OR ".join(tokens)
        ts = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank(KbChunk.search_document, ts)
        result = await self._session.execute(
            select(KbChunk.id, rank, KbChunk.heading, KbChunk.answer_verbatim, KbChunk.aliases)
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
            .order_by(rank.desc(), KbChunk.id)
            .limit(FTS_LIMIT)
        )
        scored: list[tuple[UUID, float]] = []
        for chunk_id, score, heading, answer, aliases in result.all():
            blob = f"{heading or ''} {answer or ''} {' '.join(aliases or [])}"
            if contains_injection_marker(blob):
                continue
            scored.append((chunk_id, float(score or 0.0)))
        return scored

    async def _trigram(self, site_id: UUID, visitor_text: str) -> list[tuple[UUID, float]]:
        query = (visitor_text or "").strip()
        if len(query) < 3:
            return []
        await self._session.execute(text("SET LOCAL pg_trgm.similarity_threshold = 0.30"))
        sql = text(
            f"""
            SELECT kb_chunks.id,
                   similarity({_TRGM_EXPR}, lower(:q)) AS score,
                   kb_chunks.heading,
                   kb_chunks.answer_verbatim,
                   kb_chunks.aliases
              FROM kb_chunks
              JOIN kb_pages ON kb_pages.id = kb_chunks.page_id
              JOIN kb_snapshots ON kb_snapshots.id = kb_chunks.snapshot_id
              JOIN kb_sources ON kb_sources.id = kb_pages.source_id
             WHERE kb_chunks.site_id = :site_id
               AND kb_chunks.enabled IS TRUE
               AND kb_chunks.kind <> 'refusal'
               AND kb_pages.enabled IS TRUE
               AND kb_sources.enabled IS TRUE
               AND kb_snapshots.state = 'live'
               AND {_TRGM_EXPR} % lower(:q)
             ORDER BY score DESC, kb_chunks.id
             LIMIT :fts_limit
            """
        )
        result = await self._session.execute(
            sql, {"q": query, "site_id": site_id, "fts_limit": FTS_LIMIT}
        )
        scored: list[tuple[UUID, float]] = []
        for chunk_id, score, heading, answer, aliases in result.all():
            blob = f"{heading or ''} {answer or ''} {' '.join(aliases or [])}"
            if contains_injection_marker(blob):
                continue
            scored.append((chunk_id, float(score or 0.0)))
        return scored

    async def _dense(
        self, site_id: UUID, query_vector: list[float]
    ) -> tuple[list[UUID], dict[UUID, float]]:
        await self._session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
        distance = KbChunk.embedding.cosine_distance(query_vector)
        result = await self._session.execute(
            select(
                KbChunk.id,
                KbChunk.site_id,
                KbChunk.heading,
                KbChunk.answer_verbatim,
                (1 - distance).label("cosine"),
            )
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
        for chunk_id, row_site, heading, answer, cosine in result.all():
            if row_site != site_id:
                return [], {}
            if contains_injection_marker(f"{heading or ''} {answer or ''}"):
                continue
            ids.append(chunk_id)
            scores[chunk_id] = float(cosine)
        return ids, scores

    async def _overview(self, site_id: UUID, visitor_text: str) -> list[ChunkHit]:
        result = await self._session.execute(
            select(KbChunk.id, KbChunk.answer_verbatim)
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
                KbPage.url == KbSource.start_url,
            )
            .order_by(KbPage.url, KbChunk.ordinal, KbChunk.id)
            .limit(FTS_LIMIT)
        )
        rows = result.all()
        ids = [chunk_id for chunk_id, _ in rows]
        # A brief start page may only introduce the portfolio. Supplement it
        # with existing lexical candidates rather than assuming it is complete.
        if len(ids) < KEEP:
            source_terms = " ".join(search_tokens(" ".join(answer for _, answer in rows))[:64])
            candidates = await self._fts(site_id, f"{_retrieval_text(visitor_text)} {source_terms}")
            ids = list(dict.fromkeys([*ids, *(chunk_id for chunk_id, _ in candidates)]))[:FTS_LIMIT]
        hits = {hit.id: hit for hit in await self._load(site_id, ids)}
        ordered = [hits[chunk_id] for chunk_id in ids if chunk_id in hits]
        return _cap_overview(ordered)

    async def _load(self, site_id: UUID, chunk_ids: list[UUID]) -> list[ChunkHit]:
        if not chunk_ids:
            return []
        result = await self._session.execute(
            select(KbChunk, KbPage, KbSource)
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
        for chunk, page, source in result.all():
            if chunk.site_id != site_id:
                return []
            if contains_injection_marker(chunk.answer_verbatim) or contains_injection_marker(
                chunk.heading or ""
            ):
                continue
            if is_marketing_cta(chunk.answer_verbatim):
                continue
            hits.append(self._to_hit(chunk, page, source, rrf=0.0))
        return hits

    @staticmethod
    def _to_hit(chunk: KbChunk, page: KbPage, source: KbSource, *, rrf: float) -> ChunkHit:
        origins = [url for url in (chunk.origin_urls or []) if url]
        page_url = page.public_url
        start_url = source.start_url
        url = visitor_citation_url(page_url=page_url, origin_urls=origins, start_url=start_url)
        title = urlparse(start_url).netloc if len(origins) >= 2 else page.title
        return ChunkHit(
            id=chunk.id,
            page_id=chunk.page_id,
            site_id=chunk.site_id,
            heading=chunk.heading,
            body=chunk.body,
            url=url or page_url,
            title=title or page.title,
            rrf=rrf,
            cosine=None,
            answer_verbatim=chunk.answer_verbatim,
            display_locator=None,
            snapshot_id=chunk.snapshot_id,
            canonical_question=chunk.canonical_question,
            legal_sensitive=bool(chunk.legal_sensitive),
            aliases=tuple(chunk.aliases or []),
            topic_label=chunk.topic_label or chunk.heading,
            risk_class=chunk.risk_class or "general",
            answer_mode=chunk.answer_mode or "paraphrase_allowed",
            enabled=bool(chunk.enabled),
            structured=bool(chunk.context_prefix),
        )
