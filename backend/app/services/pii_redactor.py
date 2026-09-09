"""Redact high-risk PII before Anthropic and from structured logs."""

from __future__ import annotations

from app.llm.safety_markers import OUTPUT_PII_PATTERNS

REDACTED = "[REDACTED]"
_LOG_PREVIEW = 200


def redact_for_model(text: str) -> str:
    return _apply(text or "")


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
