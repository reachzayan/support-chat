"""Exact cache for validated, history-independent grounded answers."""

from __future__ import annotations

from hashlib import sha256
from json import dumps, loads
from uuid import UUID

from app.llm.prompts import system_rules_for
from app.redis import get_redis
from app.services.bot_trace import record_trace
from app.services.grounded_response import Citation, ResponseDecision, ResponseOutcome
from app.services.kb_tokens import normalize_query
from app.settings import get_settings

_CACHE_VERSION = "grounded-v4"


def response_cache_key(
    site_id: UUID,
    site_name: str,
    snapshot_ids: list[UUID],
    visitor_text: str,
    off_brand_blocklist: list[str] | None = None,
) -> str:
    settings = get_settings()
    snapshots = ",".join(sorted(str(item) for item in snapshot_ids))
    snapshot_digest = sha256(snapshots.encode()).hexdigest()[:20]
    query_digest = sha256(
        (
            f"{_CACHE_VERSION}\0{settings.anthropic_model}\0"
            f"{system_rules_for(site_name)}\0{dumps(sorted(off_brand_blocklist or []))}\0"
            f"{normalize_query(visitor_text)}"
        ).encode()
    ).hexdigest()
    return f"bot:response:{site_id}:{snapshot_digest}:{query_digest}"


async def load_response(key: str) -> ResponseDecision | None:
    try:
        raw = await get_redis().get(key)
    except Exception:
        record_trace("response_cache", hit=False, available=False)
        return None
    if not raw:
        record_trace("response_cache", hit=False, available=True)
        return None
    try:
        payload = loads(raw)
        citations = [
            Citation(
                chunk_id=UUID(item["chunk_id"]),
                snapshot_id=UUID(item["snapshot_id"]) if item["snapshot_id"] else None,
                response_start=int(item["response_start"]),
                response_end=int(item["response_end"]),
                source_start=int(item["source_start"]),
                source_end=int(item["source_end"]),
                cited_text=str(item["cited_text"]),
                source_title=str(item["source_title"]),
                source_url=str(item["source_url"]),
            )
            for item in payload["citations"]
        ]
        body = str(payload["body"])
        if not body or not citations:
            raise ValueError("empty_cached_answer")
    except (KeyError, TypeError, ValueError):
        record_trace("response_cache", hit=False, available=True, invalid=True)
        return None
    record_trace("response_cache", hit=True, available=True)
    return ResponseDecision(
        ResponseOutcome.SYNTHESIZED_ANSWER,
        "response_cache",
        body,
        citations=citations,
    )


async def store_response(key: str, decision: ResponseDecision) -> None:
    if (
        decision.outcome is not ResponseOutcome.SYNTHESIZED_ANSWER
        or not decision.citations
        or decision.reason_code is not None
        or decision.offer_handoff
    ):
        return
    payload = {
        "body": decision.body,
        "citations": [
            {
                "chunk_id": str(item.chunk_id),
                "snapshot_id": str(item.snapshot_id) if item.snapshot_id else None,
                "response_start": item.response_start,
                "response_end": item.response_end,
                "source_start": item.source_start,
                "source_end": item.source_end,
                "cited_text": item.cited_text,
                "source_title": item.source_title,
                "source_url": item.source_url,
            }
            for item in decision.citations
        ],
    }
    try:
        await get_redis().set(
            key,
            dumps(payload, separators=(",", ":")),
            ex=get_settings().grounded_response_cache_ttl,
        )
    except Exception:
        record_trace("response_cache", stored=False)
        return
    record_trace("response_cache", stored=True)
