"""Status history — oracles are hand-counted from seeded samples.

Overall uptime is the worst service in the window, rounded to one decimal.
A 91-day-old outage is outside the 90-day window. Bars are UTC calendar days,
oldest first. Hourly medians are oldest-first with the current hour last.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import redis as redis_sync
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.workers.health import HEARTBEAT_KEY
from tests.conftest import DEFAULT_TEST_REDIS_URL
from tests.knowledge_gap_fixtures import db
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    EASY_PUBLIC_KEY,
    HOST_ORIGIN,
    insert_site,
    insert_staff,
    login_staff,
)

DAY = timedelta(days=1)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _set_worker_heartbeat() -> None:
    client = redis_sync.Redis.from_url(os.environ.get("REDIS_URL", DEFAULT_TEST_REDIS_URL))
    try:
        client.set(HEARTBEAT_KEY, "1", ex=30)
    finally:
        client.close()


def _staff(client: TestClient) -> str:
    insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    _set_worker_heartbeat()
    return login_staff(client, ALEX_EMAIL, ALEX_PASSWORD)


def _add_sample(
    session,
    *,
    service: str,
    ok: bool,
    created_at: datetime,
    latency_ms: int | None = None,
) -> None:
    session.execute(
        text(
            "INSERT INTO status_samples (service, ok, latency_ms, created_at) "
            "VALUES (:service, :ok, :latency_ms, :created_at)"
        ),
        {
            "service": service,
            "ok": ok,
            "latency_ms": latency_ms,
            "created_at": created_at,
        },
    )


def _seed_history() -> None:
    """Worked example used by the history tests.

    Postgres: 4 ok + 1 down in the last few hours (80% over 24h);
    5 ok three days ago (9/10 = 90% over 7d and 30d);
    10 ok forty days ago (19/20 = 95% over 90d);
    1 down ninety-one days ago (must not count).
    Redis: 5 ok in the last few hours (100% in every window).
    Latency: current hour 10, 20, 30 ms (median 20); previous hour 42 ms.
    """
    now = _utc_now()
    hour = now.replace(minute=0, second=0, microsecond=0)
    with db() as session:
        _add_sample(session, service="postgres", ok=True, created_at=now, latency_ms=10)
        _add_sample(session, service="postgres", ok=True, created_at=now, latency_ms=20)
        _add_sample(session, service="postgres", ok=True, created_at=now, latency_ms=30)
        _add_sample(
            session,
            service="postgres",
            ok=True,
            created_at=hour - timedelta(minutes=30),
            latency_ms=42,
        )
        _add_sample(session, service="postgres", ok=False, created_at=now)
        for index in range(5):
            _add_sample(
                session,
                service="postgres",
                ok=True,
                created_at=now - 3 * DAY - timedelta(minutes=index),
                latency_ms=8,
            )
        for index in range(10):
            _add_sample(
                session,
                service="postgres",
                ok=True,
                created_at=now - 40 * DAY - timedelta(minutes=index),
                latency_ms=8,
            )
        _add_sample(session, service="postgres", ok=False, created_at=now - 91 * DAY)
        for index in range(5):
            _add_sample(
                session,
                service="redis",
                ok=True,
                created_at=now - timedelta(minutes=index + 1),
                latency_ms=4,
            )


def _monitor(body: dict, key: str) -> dict:
    return next(row for row in body["monitors"] if row["key"] == key)


def test_empty_history_does_not_invent_uptime(client: TestClient) -> None:
    token = _staff(client)

    body = client.get("/api/status", headers=_auth(token)).json()

    assert body["uptime"] == {
        "hours_24": None,
        "days_7": None,
        "days_30": None,
        "days_90": None,
    }
    assert _monitor(body, "postgres")["availability_30d"] == ["empty"] * 30
    assert _monitor(body, "postgres")["latency_24h"] == [None] * 24
    assert [row["summary"] for row in body["incidents"]] == ["No incidents"] * 7


def test_uptime_windows_use_the_worst_service_and_ignore_91_day_outages(
    client: TestClient,
) -> None:
    token = _staff(client)
    _seed_history()

    body = client.get("/api/status", headers=_auth(token)).json()

    assert body["uptime"] == {
        "hours_24": 80.0,
        "days_7": 90.0,
        "days_30": 90.0,
        "days_90": 95.0,
    }


def test_thirty_day_bars_mark_today_degraded_and_three_days_ago_up(client: TestClient) -> None:
    token = _staff(client)
    _seed_history()

    body = client.get("/api/status", headers=_auth(token)).json()
    postgres = _monitor(body, "postgres")
    bars = postgres["availability_30d"]
    assert len(bars) == 30
    assert bars[-1] == "degraded"
    assert bars[-4] == "up"
    assert bars[0] == "empty"
    assert _monitor(body, "api")["availability_30d"] == ["empty"] * 30
    assert postgres["name"] == "Postgres"
    assert _monitor(body, "worker")["name"] == "Background work"


def test_hourly_median_latency_is_20_this_hour_and_42_last_hour(client: TestClient) -> None:
    token = _staff(client)
    _seed_history()

    body = client.get("/api/status", headers=_auth(token)).json()
    hours = _monitor(body, "postgres")["latency_24h"]
    assert len(hours) == 24
    assert hours[-1] == 20.0
    assert hours[-2] == 42.0


def test_incidents_name_today_as_postgres_down_and_the_other_six_days_clear(
    client: TestClient,
) -> None:
    token = _staff(client)
    _seed_history()

    body = client.get("/api/status", headers=_auth(token)).json()
    days = body["incidents"]
    assert len(days) == 7
    assert days[0]["date"] == _utc_now().date().isoformat()
    assert days[0]["summary"] == "Postgres was down"
    assert [row["summary"] for row in days[1:]] == ["No incidents"] * 6
