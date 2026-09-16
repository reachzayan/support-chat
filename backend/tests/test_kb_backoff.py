from datetime import UTC, datetime, timedelta

from app.services.kb_backoff import (
    classify_error,
    next_backoff_seconds,
    next_run_at,
    should_dead_letter,
)


def test_timeout_and_rate_limit_are_transient() -> None:
    assert classify_error("timeout") == "transient"
    assert classify_error("rate_limit") == "transient"
    assert classify_error("overload") == "transient"
    assert classify_error("embed") == "transient"
    assert classify_error("http") == "transient"


def test_ssrf_oversize_and_client_errors_are_permanent() -> None:
    assert classify_error("ssrf") == "permanent"
    assert classify_error("too_large") == "permanent"
    assert classify_error("oversize") == "permanent"
    assert classify_error("robots") == "permanent"
    assert classify_error("non_html") == "permanent"
    assert classify_error("http_4xx") == "permanent"
    assert classify_error("browser") == "permanent"


def test_browser_crash_is_transient() -> None:
    assert classify_error("browser_crash") == "transient"


def test_empty_and_injection_are_content_drop() -> None:
    assert classify_error("empty") == "content_drop"
    assert classify_error("injection") == "content_drop"
    assert classify_error("hallucination") == "content_drop"


def test_backoff_doubles_until_300_with_unit_jitter() -> None:
    # jitter=0.5 => multiplier 1.0, so delay is exactly min(2^attempt, 300)
    assert next_backoff_seconds(0, jitter=0.5) == 1.0
    assert next_backoff_seconds(1, jitter=0.5) == 2.0
    assert next_backoff_seconds(2, jitter=0.5) == 4.0
    assert next_backoff_seconds(3, jitter=0.5) == 8.0
    assert next_backoff_seconds(8, jitter=0.5) == 256.0
    assert next_backoff_seconds(9, jitter=0.5) == 300.0


def test_backoff_floor_is_half_when_jitter_is_zero() -> None:
    assert next_backoff_seconds(3, jitter=0.0) == 4.0


def test_next_run_at_is_now_plus_backoff() -> None:
    now = datetime(2026, 9, 11, 14, 0, tzinfo=UTC)
    stamp = next_run_at(now, attempt=2, jitter=0.5)
    assert stamp == now + timedelta(seconds=4)


def test_dead_letter_after_five_transient_attempts() -> None:
    assert should_dead_letter("transient", attempts=4, max_attempts=5) is False
    assert should_dead_letter("transient", attempts=5, max_attempts=5) is True
    assert should_dead_letter("permanent", attempts=1, max_attempts=5) is True
    assert should_dead_letter("content_drop", attempts=1, max_attempts=5) is False
