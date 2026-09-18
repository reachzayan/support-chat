"""Marketing CTA helpers shared by hybrid retrieval and corpus filters."""

from __future__ import annotations

import re
import unicodedata

_PUNCT_RE = re.compile(r"[^\w\s?]", re.UNICODE)
_CTA_SNIPPETS = (
    "talk to a specialist",
    "get in touch",
    "jump into the portal",
)


def is_marketing_cta(text: str) -> bool:
    body = " ".join((text or "").casefold().split())
    return body in _CTA_SNIPPETS


def normalize_fast_query(value: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.casefold()
    normalized = _PUNCT_RE.sub(" ", normalized)
    normalized = " ".join(normalized.split())
    if len(normalized) < 3:
        return None
    return normalized
