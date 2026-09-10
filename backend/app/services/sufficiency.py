from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.llm.bot_responder import BufferedAnswer

Outcome = Literal["answer", "clarify", "insufficient", "policy_boundary", "tech_fail"]

_NUMERIC_CLAIM_RE = re.compile(
    r"\b\d+(?:[-\u2013]\d+)?\s*(?:hours?|days?|minutes?|business days?|%|\$\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SufficiencyDecision:
    outcome: Outcome
    reason: str
    clarification: str | None = None


@dataclass(frozen=True)
class CitedUnit:
    id: UUID
    answer_verbatim: str
    url: str
    legal_sensitive: bool = False
    enabled: bool = True
    snapshot_live: bool = True


def evaluate(
    answer: BufferedAnswer | None,
    *,
    cited_units: list[CitedUnit],
    live_urls: set[str],
    provider_error: bool = False,
    visitor_sensitive: bool = False,
) -> SufficiencyDecision:
    if provider_error or answer is None or not (answer.body or "").strip():
        return SufficiencyDecision(outcome="tech_fail", reason="empty_or_provider_error")

    if visitor_sensitive or any(unit.legal_sensitive for unit in cited_units):
        return SufficiencyDecision(outcome="policy_boundary", reason="legal_sensitive")

    cited_ids = list(answer.source_chunk_ids or [])
    if not cited_ids:
        return SufficiencyDecision(outcome="insufficient", reason="no_citation")

    by_id = {unit.id: unit for unit in cited_units}
    for chunk_id in cited_ids:
        unit = by_id.get(chunk_id)
        if unit is None or not unit.enabled or not unit.snapshot_live:
            return SufficiencyDecision(outcome="insufficient", reason="stale_citation")
        if unit.url and unit.url not in live_urls:
            return SufficiencyDecision(outcome="insufficient", reason="stale_citation")

    body = answer.body.strip()
    cited_text = "\n".join(
        by_id[chunk_id].answer_verbatim for chunk_id in cited_ids if chunk_id in by_id
    )
    for claim in _NUMERIC_CLAIM_RE.findall(body):
        needle = " ".join(claim.casefold().split())
        haystack = " ".join(cited_text.casefold().split())
        if needle not in haystack:
            return SufficiencyDecision(outcome="insufficient", reason="unsupported_numeric")

    if "?" in body and len(body) <= 120:
        return SufficiencyDecision(
            outcome="clarify",
            reason="short_clarifying_question",
            clarification=body,
        )

    return SufficiencyDecision(outcome="answer", reason="grounded")
