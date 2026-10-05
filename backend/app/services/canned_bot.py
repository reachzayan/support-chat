"""Retrieve bot-eligible canned replies and send a winning row verbatim."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canned_reply import CannedReply
from app.models.visitor import Visitor
from app.repositories.canned_reply_repo import CannedReplyRepository
from app.services.canned_import import has_unfilled_fields
from app.services.grounded_response_types import ProviderStatus, ResponseDecision, ResponseOutcome
from app.services.kb_embedder import Embedder, default_embedder, rrf_merge
from app.services.kb_hybrid import HybridKbSearch
from app.services.kb_tokens import WEAK_OVERLAP, search_tokens, tokenize
from app.services.route_decision import live_snapshots_for_site

log = structlog.get_logger("canned_bot")

FTS_LIMIT = 20
DENSE_LIMIT = 20
CANNED_COSINE_FLOOR = 0.55
CANNED_COSINE_GAP = 0.08
# A visitor "yes" or "no" only means something as the answer to a question the bot just asked.
# Scripts named after an answer (der_yes_followup) therefore match these words only when they
# are linked to the question they follow; elsewhere the words are ignored.
ANSWER_WORDS = frozenset({"yes", "no", "not", "sure"})
# Phrase rewrites in tokenize() land on these tokens. A row that does not carry the topic
# must not win just because it shares "DOT" or "report" with the question.
CANNED_QUERY_TOPICS = frozenset({"pricing", "turnaround", "interpretation", "setup"})
HANDOFF_REASON = "individual_case"
_SPACE = re.compile(r"[ \t]{2,}")
_COLLISION_SUFFIX = re.compile(r"-\d+$")


@dataclass(frozen=True)
class CannedHit:
    id: UUID
    shortcut: str
    body: str
    rrf: float
    cosine: float | None
    lexical: bool
    aliases: tuple[str, ...] = ()
    follow_up: bool = False
    hands_off: bool = False


def canned_embed_text(shortcut: str, aliases: list[str], body: str) -> str:
    keys = " ".join([shortcut, *aliases])
    return f"{keys}\n{body}"


def fill_canned_variables(
    body: str,
    *,
    customer_name: str = "",
    customer_email: str = "",
    agent_name: str = "",
    agent_email: str = "",
) -> str:
    filled = (
        body.replace("%customer-name%", (customer_name or "").strip())
        .replace("%customer-email%", (customer_email or "").strip())
        .replace("%agent-name%", (agent_name or "").strip())
        .replace("%agent-email%", (agent_email or "").strip())
    )
    filled = _SPACE.sub(" ", filled)
    return "\n".join(line.rstrip() for line in filled.splitlines()).strip()


def _shortcut_key_text(shortcut: str, aliases: list[str] | tuple[str, ...]) -> str:
    primary = _COLLISION_SUFFIX.sub("", shortcut)
    return " ".join((primary.replace("_", " ").replace("-", " "), *aliases))


def _key_tokens(shortcut: str, aliases: list[str] | tuple[str, ...], follow_up: bool) -> set[str]:
    keys = set(tokenize(_shortcut_key_text(shortcut, aliases)))
    return keys if follow_up else keys - ANSWER_WORDS


def lexical_shortcut_match(
    visitor_text: str, shortcut: str, aliases: list[str], follow_up: bool = False
) -> bool:
    query = set(tokenize(visitor_text))
    keys = _key_tokens(shortcut, aliases, follow_up)
    strong = (query & keys) - WEAK_OVERLAP
    return bool(strong)


def lexical_specificity(
    visitor_text: str,
    shortcut: str,
    aliases: list[str] | tuple[str, ...],
    follow_up: bool = False,
) -> float:
    keys = _key_tokens(shortcut, aliases, follow_up)
    if not keys:
        return 0.0
    query = set(tokenize(visitor_text))
    strong = (query & keys) - WEAK_OVERLAP
    if not strong:
        return 0.0
    return len(strong) / len(keys)


def pick_canned_winner(
    hits: list[CannedHit], *, best_kb_cosine: float | None, visitor_text: str
) -> CannedHit | None:
    if not hits:
        return None
    lexical = [hit for hit in hits if decisive_lexical_hit(hit, visitor_text)]
    if lexical:
        return max(lexical, key=lambda hit: _lexical_rank(hit, visitor_text))
    scored = [hit for hit in hits if hit.cosine is not None]
    if not scored:
        return None
    ranked = sorted(scored, key=lambda hit: (-hit.cosine, str(hit.id)))
    best = ranked[0]
    if best.cosine is None or best.cosine < CANNED_COSINE_FLOOR:
        return None
    if best_kb_cosine is not None and best.cosine <= best_kb_cosine:
        return None
    second = ranked[1] if len(ranked) > 1 else None
    next_cosine = second.cosine if second is not None and second.cosine is not None else 0.0
    if best.cosine - next_cosine < CANNED_COSINE_GAP:
        return None
    return best


def decisive_lexical_hit(hit: CannedHit, visitor_text: str) -> bool:
    if not hit.lexical:
        return False
    keys = _key_tokens(hit.shortcut, hit.aliases, hit.follow_up)
    topics = set(tokenize(visitor_text)) & CANNED_QUERY_TOPICS
    if topics and not (topics & keys):
        return False
    if lexical_specificity(visitor_text, hit.shortcut, hit.aliases, hit.follow_up) >= 0.5:
        return True
    return len(set(tokenize(visitor_text))) <= 2


def _lexical_rank(hit: CannedHit, visitor_text: str) -> tuple[float, float]:
    spec = lexical_specificity(visitor_text, hit.shortcut, hit.aliases, hit.follow_up)
    similarity = hit.cosine if hit.cosine is not None else 0.0
    return (spec * (1.0 + similarity), hit.rrf)


def canned_embedder() -> Embedder:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        from app.services.kb_embedder import FakeEmbedder

        return FakeEmbedder()
    return default_embedder()


async def refresh_canned_embedding(reply: CannedReply, embedder: Embedder) -> None:
    if not reply.enabled or not reply.bot_eligible:
        reply.embedding = None
        reply.embedder_id = None
        return
    vectors = await embedder.embed_documents(
        [canned_embed_text(reply.shortcut, list(reply.aliases or []), reply.body)]
    )
    reply.embedding = vectors[0]
    reply.embedder_id = embedder.embedder_id


async def embed_replies(replies: list[CannedReply], embedder: Embedder | None = None) -> None:
    if not replies:
        return
    worker = embedder if embedder is not None else canned_embedder()
    pending = [reply for reply in replies if reply.enabled and reply.bot_eligible]
    for reply in replies:
        if reply not in pending:
            reply.embedding = None
            reply.embedder_id = None
    if not pending:
        return
    try:
        vectors = await worker.embed_documents(
            [
                canned_embed_text(reply.shortcut, list(reply.aliases or []), reply.body)
                for reply in pending
            ]
        )
        for reply, vector in zip(pending, vectors, strict=True):
            reply.embedding = vector
            reply.embedder_id = worker.embedder_id
    except Exception as exc:
        # A vector left over from the old wording would mislead search, so clear it. The worker
        # re-embeds these rows on its next pass (refresh_stale_embeddings).
        for reply in pending:
            reply.embedding = None
            reply.embedder_id = None
        log.warning("canned_embed_failed", count=len(pending), error_class=type(exc).__name__)


async def refresh_stale_embeddings(session: AsyncSession, embedder: Embedder, limit: int) -> int:
    """Embed usable rows that have no vector or one from another model. Returns rows fixed."""
    rows = await CannedReplyRepository(session).list_needing_embedding(embedder.embedder_id, limit)
    if not rows:
        return 0
    await embed_replies(rows, embedder)
    await session.commit()
    return sum(1 for row in rows if row.embedder_id == embedder.embedder_id)


def _in_context(rows: list[CannedReply], previous_locator: str | None) -> list[CannedReply]:
    """Drop follow-ups unless the bot's last message was the script they follow."""
    shortcut_by_id = {row.id: row.shortcut for row in rows}

    def available(row: CannedReply) -> bool:
        if row.follows_id is None:
            return True
        parent = shortcut_by_id.get(row.follows_id)
        return parent is not None and previous_locator == f"#{parent}"

    return [row for row in rows if available(row)]


async def search_canned(
    session: AsyncSession,
    embedder: Embedder,
    site_id: UUID,
    visitor_text: str,
    previous_locator: str | None = None,
) -> list[CannedHit]:
    # Rows already imported, or switched on by staff, may still hold agent fill-in fields.
    usable = [
        row
        for row in await CannedReplyRepository(session).list_bot_eligible(site_id)
        if not has_unfilled_fields(row.body)
    ]
    rows = _in_context(usable, previous_locator)
    if not rows:
        return []
    by_id = {row.id: row for row in rows}
    eligible_ids = list(by_id)
    fts_ids = await _fts_ids(session, visitor_text, eligible_ids)
    query_vector = await _query_vector(embedder, visitor_text)
    dense_ids, cosine_by_id = await _dense_ids(
        session, eligible_ids, query_vector, embedder.embedder_id
    )
    ranked = rrf_merge(fts_ids, dense_ids)
    hits: list[CannedHit] = []
    seen: set[UUID] = set()
    for reply_id, rrf in ranked:
        row = by_id.get(reply_id)
        if row is None:
            continue
        seen.add(reply_id)
        hits.append(_to_hit(row, rrf, cosine_by_id.get(reply_id), visitor_text))
    for row in rows:
        if row.id in seen:
            continue
        follow_up = row.follows_id is not None
        if lexical_shortcut_match(visitor_text, row.shortcut, list(row.aliases or []), follow_up):
            hits.append(_to_hit(row, 0.0, cosine_by_id.get(row.id), visitor_text))
    return hits


async def canned_reply_decision(
    session: AsyncSession,
    embedder: Embedder,
    site_id: UUID,
    visitor_text: str,
    visitor: Visitor | None,
    previous_locator: str | None = None,
) -> ResponseDecision | None:
    hits = await search_canned(session, embedder, site_id, visitor_text, previous_locator)
    if not hits:
        return None
    best_kb_cosine = None
    if not any(decisive_lexical_hit(hit, visitor_text) for hit in hits):
        best_kb_cosine = await _best_kb_cosine(session, embedder, site_id, visitor_text)
    winner = pick_canned_winner(hits, best_kb_cosine=best_kb_cosine, visitor_text=visitor_text)
    if winner is None:
        return None
    log.info("canned_turn", canned_id=str(winner.id), shortcut=winner.shortcut)
    body = fill_canned_variables(
        winner.body,
        customer_name=visitor.name if visitor is not None else "",
        customer_email=visitor.email if visitor is not None else "",
    )
    return ResponseDecision(
        ResponseOutcome.SYNTHESIZED_ANSWER,
        "canned_reply",
        body,
        provider_status=ProviderStatus.NOT_USED,
        display_locator=f"#{winner.shortcut}",
        handoff_reason=HANDOFF_REASON if winner.hands_off else None,
    )


async def inspect_canned_search(
    session: AsyncSession,
    embedder: Embedder,
    site_id: UUID,
    visitor_text: str,
) -> dict[str, object]:
    hits = await search_canned(session, embedder, site_id, visitor_text)
    best_kb_cosine = None
    if hits and not any(decisive_lexical_hit(hit, visitor_text) for hit in hits):
        best_kb_cosine = await _best_kb_cosine(session, embedder, site_id, visitor_text)
    winner = pick_canned_winner(hits, best_kb_cosine=best_kb_cosine, visitor_text=visitor_text)
    return {
        "winner": None if winner is None else winner.shortcut,
        "best_kb_cosine": best_kb_cosine,
        "hits": [
            {
                "shortcut": hit.shortcut,
                "lexical": hit.lexical,
                "rrf": hit.rrf,
                "cosine": hit.cosine,
            }
            for hit in hits[:8]
        ],
    }


def _to_hit(
    row: CannedReply, rrf: float, cosine_score: float | None, visitor_text: str
) -> CannedHit:
    follow_up = row.follows_id is not None
    return CannedHit(
        id=row.id,
        shortcut=row.shortcut,
        body=row.body,
        rrf=rrf,
        cosine=cosine_score,
        aliases=tuple(row.aliases or []),
        lexical=lexical_shortcut_match(
            visitor_text, row.shortcut, list(row.aliases or []), follow_up
        ),
        follow_up=follow_up,
        hands_off=row.hands_off,
    )


async def _query_vector(embedder: Embedder, visitor_text: str) -> list[float] | None:
    try:
        return await embedder.embed_query(visitor_text)
    except Exception:
        log.info("canned_embed_query_failed")
        return None


async def _fts_ids(
    session: AsyncSession, visitor_text: str, eligible_ids: list[UUID]
) -> list[UUID]:
    tokens = search_tokens(visitor_text)
    if not tokens:
        return []
    ts = func.websearch_to_tsquery("english", " OR ".join(tokens))
    rank = func.ts_rank(CannedReply.search_document, ts)
    result = await session.execute(
        select(CannedReply.id)
        .where(
            CannedReply.id.in_(eligible_ids),
            CannedReply.search_document.op("@@")(ts),
        )
        .order_by(rank.desc(), CannedReply.id)
        .limit(FTS_LIMIT)
    )
    return list(result.scalars().all())


async def _dense_ids(
    session: AsyncSession,
    eligible_ids: list[UUID],
    query_vector: list[float] | None,
    embedder_id: str,
) -> tuple[list[UUID], dict[UUID, float]]:
    if query_vector is None:
        return [], {}
    distance = CannedReply.embedding.cosine_distance(query_vector)
    result = await session.execute(
        select(CannedReply.id, distance)
        .where(
            CannedReply.id.in_(eligible_ids),
            CannedReply.embedding.is_not(None),
            # Vectors from another model live in a different space; their scores mean nothing here.
            CannedReply.embedder_id == embedder_id,
        )
        .order_by(distance, CannedReply.id)
        .limit(DENSE_LIMIT)
    )
    ids: list[UUID] = []
    cosine_by_id: dict[UUID, float] = {}
    for reply_id, dist in result.all():
        similarity = 1.0 - float(dist if dist is not None else 1.0)
        ids.append(reply_id)
        cosine_by_id[reply_id] = similarity
    return ids, cosine_by_id


async def _best_kb_cosine(
    session: AsyncSession,
    embedder: Embedder,
    site_id: UUID,
    visitor_text: str,
) -> float | None:
    snapshots = await live_snapshots_for_site(session, site_id)
    if not snapshots:
        return None
    hits = await HybridKbSearch(session).search_with_deferred_embed(embedder, site_id, visitor_text)
    scores = [hit.cosine for hit in hits if hit.cosine is not None]
    if not scores:
        return None
    return max(scores)
