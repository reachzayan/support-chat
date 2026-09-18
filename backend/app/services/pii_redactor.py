"""Redact high-risk PII before Anthropic and from structured logs."""

from __future__ import annotations

from app.llm.safety_markers import OUTPUT_PII_PATTERNS

REDACTED = "[REDACTED]"
_LOG_PREVIEW = 200


def redact_for_model(text: str) -> str:
    return _apply(text or "")


def redact_evidence(text: str) -> str:
    """Retain public KB contacts; still mask regulated personal identifiers.

    Only controlled KB documents use this. Visitor input and history always
    use redact_for_model. Output contacts must also occur in cited KB text.
    """
    out = text or ""
    for pattern in OUTPUT_PII_PATTERNS[:-2]:
        out = pattern.sub(REDACTED, out)
    return out


def redact_for_log(text: str) -> str:
    masked = _apply(text or "")
    if len(masked) > _LOG_PREVIEW:
        return masked[:_LOG_PREVIEW]
    return masked


def _apply(text: str) -> str:
    out = text
    for pattern in OUTPUT_PII_PATTERNS:
        out = pattern.sub(REDACTED, out)
    return out
