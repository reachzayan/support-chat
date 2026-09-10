"""Deterministic off-topic / competitor-brand detector."""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.services.kb_tokens import tokenize

_WORD_RE = re.compile(r"[a-z0-9]+")
DEFAULT_JACCARD = 0.05


def _normalize(text: str) -> str:
    return " ".join((text or "").casefold().split())


def _token_set(text: str) -> set[str]:
    tokens = tokenize(text) if text else []
    if tokens:
        return set(tokens)
    return set(_WORD_RE.findall(_normalize(text)))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def is_off_topic(
    visitor_text: str,
    *,
    blocklist: Iterable[str],
    evidence_bodies: Iterable[str],
    threshold: float = DEFAULT_JACCARD,
) -> bool:
    """True when visitor mentions a blocklisted brand and does not overlap evidence."""
    normalized = _normalize(visitor_text)
    if not normalized:
        return False
    tokens = [item.strip().casefold() for item in blocklist if item and item.strip()]
    if not tokens:
        return False
    if not any(token in normalized for token in tokens):
        return False

    visitor_tokens = _token_set(visitor_text)
    best = 0.0
    for body in evidence_bodies:
        score = jaccard(visitor_tokens, _token_set(body))
        if score > best:
            best = score
        if best >= threshold:
            return False
    return True
