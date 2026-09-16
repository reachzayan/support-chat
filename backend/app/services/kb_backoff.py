from datetime import datetime, timedelta

TRANSIENT_CODES = frozenset(
    {
        "timeout",
        "rate_limit",
        "overload",
        "embed",
        "http",
        "ingest",
        "browser_crash",
    }
)
PERMANENT_CODES = frozenset(
    {
        "ssrf",
        "too_large",
        "oversize",
        "robots",
        "non_html",
        "http_4xx",
        "browser",
    }
)
CONTENT_DROP_CODES = frozenset({"empty", "injection", "hallucination"})


def classify_error(code: str) -> str:
    if code in CONTENT_DROP_CODES:
        return "content_drop"
    if code in PERMANENT_CODES:
        return "permanent"
    if code in TRANSIENT_CODES:
        return "transient"
    return "transient"


def next_backoff_seconds(attempt: int, *, jitter: float = 0.5, max_seconds: int = 300) -> float:
    base = min(2 ** max(attempt, 0), max_seconds)
    factor = 0.5 + max(0.0, min(jitter, 0.5))
    return float(base) * factor


def next_run_at(now: datetime, attempt: int, *, jitter: float = 0.5) -> datetime:
    return now + timedelta(seconds=next_backoff_seconds(attempt, jitter=jitter))


def should_dead_letter(error_class: str, attempts: int, max_attempts: int = 5) -> bool:
    if error_class == "permanent":
        return True
    if error_class == "content_drop":
        return False
    return attempts >= max_attempts
