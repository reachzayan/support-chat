"""Staff status board — oracles are hand-counted from the seeded desk.

A visitor-facing or unsigned request must not see the board. Counts are chats,
not messages. Closed-yesterday and prechat chats are not desk load. Disabled
knowledge sources do not stain a website. Redis failures name the service
without leaking connection details.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import redis as redis_sync
from fastapi.testclient import TestClient

from app.chat.connection_manager import AgentConnection, VisitorConnection, connection_manager
from app.models.app_log import AppLog
from app.models.conversation import Conversation
from app.models.kb_source import KbSource
from app.models.knowledge_gap import KnowledgeGap
from app.models.site import Site
from app.models.visitor import Visitor
from app.workers.health import HEARTBEAT_KEY
from tests.conftest import DEFAULT_TEST_REDIS_URL
from tests.knowledge_gap_fixtures import db
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    BG_PUBLIC_KEY,
    EASY_PUBLIC_KEY,
    HOST_ORIGIN,
    insert_site,
    insert_staff,
    login_staff,
)

NOW = datetime.now(UTC)
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _set_worker_heartbeat(healthy: bool) -> None:
    client = redis_sync.Redis.from_url(os.environ.get("REDIS_URL", DEFAULT_TEST_REDIS_URL))
    try:
        if healthy:
            client.set(HEARTBEAT_KEY, "1", ex=30)
        else:
            client.delete(HEARTBEAT_KEY)
    finally:
        client.close()


def _seed_chat(
    session,
    site_id: uuid.UUID,
    state: str,
    *,
    closed_at: datetime | None = None,
    assigned_agent_id: uuid.UUID | None = None,
) -> None:
    visitor = Visitor(site_id=site_id, resume_token_hash=uuid.uuid4().hex, name="Ada Lopez")
    session.add(visitor)
    session.flush()
    session.add(
        Conversation(
            site_id=site_id,
            visitor_id=visitor.id,
            state=state,
            assigned_agent_id=assigned_agent_id,
            closed_at=closed_at,
        )
    )


def _seed_source(session, site_id: uuid.UUID, status: str, *, enabled: bool = True) -> None:
    session.add(
        KbSource(
            site_id=site_id,
            start_url=f"https://kb.test/{uuid.uuid4().hex}",
            mode="list",
            seed_urls=[],
            status=status,
            enabled=enabled,
        )
    )


def _desk(client: TestClient) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str]:
    """Worked example used by the payload tests.

    SampleSite: 2 waiting, 1 with the assistant, 1 closed today, 1 closed yesterday,
    1 prechat (ignored), 1 enabled failed source, 1 disabled failed source,
    widget installed, 1 open gap + 1 dismissed gap.
    Sample Services: 1 live with a specialist, 1 ready source, widget never seen.
    Logs: 2 errors in the last hour, 1 warning, 1 error from three days ago.
    """
    easy_id = insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    background_id = insert_site(
        "backgroundchecks", "Sample Services", BG_PUBLIC_KEY, [HOST_ORIGIN]
    )
    alex_id = insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    with db() as session:
        easy = session.get(Site, easy_id)
        assert easy is not None
        easy.widget_installed = True
        _seed_chat(session, easy_id, "queued")
        _seed_chat(session, easy_id, "queued")
        _seed_chat(session, easy_id, "bot")
        _seed_chat(session, easy_id, "prechat")
        _seed_chat(session, easy_id, "closed", closed_at=NOW)
        _seed_chat(session, easy_id, "closed", closed_at=NOW - DAY)
        _seed_chat(session, background_id, "human", assigned_agent_id=alex_id)
        _seed_source(session, easy_id, "failed", enabled=True)
        _seed_source(session, easy_id, "failed", enabled=False)
        _seed_source(session, background_id, "ready", enabled=True)
        session.add(KnowledgeGap(site_id=easy_id, question="How do I enroll a driver?"))
        session.add(
            KnowledgeGap(site_id=easy_id, question="Old dismissed question", status="dismissed")
        )
        session.add(
            AppLog(
                level="error",
                source="backend",
                logger_name="kb.pipeline",
                event="ingest_page_failed",
                message="Fetch timed out for knowledge page",
                created_at=NOW - timedelta(minutes=10),
            )
        )
        session.add(
            AppLog(
                level="error",
                source="frontend",
                logger_name="frontend",
                event="ui_window_error",
                message="Unhandled window error",
                created_at=NOW - timedelta(minutes=40),
            )
        )
        session.add(
            AppLog(
                level="warning",
                source="backend",
                logger_name="chat",
                event="replay_skipped",
                message="Catch-up skipped a stale cursor",
                created_at=NOW - timedelta(minutes=5),
            )
        )
        session.add(
            AppLog(
                level="error",
                source="backend",
                logger_name="kb.pipeline",
                event="ingest_page_failed",
                message="Old crawl failure",
                created_at=NOW - timedelta(days=3),
            )
        )
    token = login_staff(client, ALEX_EMAIL, ALEX_PASSWORD)
    return easy_id, background_id, alex_id, token


def test_unsigned_requests_cannot_read_the_status_board(client: TestClient) -> None:
    assert client.get("/api/status").status_code == 401


def test_desk_snapshot_uses_hand_counted_chats_and_flags_failed_knowledge(
    client: TestClient,
) -> None:
    easy_id, background_id, _, token = _desk(client)
    _set_worker_heartbeat(True)

    response = client.get("/api/status", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["overall"] == "attention"
    assert body["headline"] == "Knowledge ingest failed"
    assert body["services"] == {
        "api": "ok",
        "postgres": "ok",
        "redis": "ok",
        "worker": "ok",
    }
    assert body["inbox"] == {"waiting": 2, "bot": 1, "live": 1, "closed_today": 1}
    assert body["knowledge"] == {"ready": 1, "running": 0, "failed": 1, "queued": 0}
    assert body["gaps_open"] == 1
    assert body["errors_24h"] == 2
    assert [row["event"] for row in body["recent_errors"]] == [
        "ingest_page_failed",
        "ui_window_error",
    ]
    assert body["recent_errors"][0]["message"] == "Fetch timed out for knowledge page"
    by_key = {row["key"]: row for row in body["sites"]}
    assert by_key["samplesite"]["id"] == str(easy_id)
    assert by_key["samplesite"]["name"] == "SampleSite"
    assert by_key["samplesite"]["waiting"] == 2
    assert by_key["samplesite"]["knowledge"] == "failed"
    assert by_key["samplesite"]["widget_installed"] is True
    assert by_key["backgroundchecks"]["id"] == str(background_id)
    assert by_key["backgroundchecks"]["waiting"] == 0
    assert by_key["backgroundchecks"]["knowledge"] == "ready"
    assert by_key["backgroundchecks"]["widget_installed"] is None


def test_healthy_desk_with_no_failed_ingest_is_all_clear(client: TestClient) -> None:
    insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    token = login_staff(client, ALEX_EMAIL, ALEX_PASSWORD)
    _set_worker_heartbeat(True)

    response = client.get("/api/status", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["overall"] == "ok"
    assert body["headline"] == "All systems answering"
    assert body["inbox"] == {"waiting": 0, "bot": 0, "live": 0, "closed_today": 0}
    assert body["knowledge"]["failed"] == 0
    assert body["errors_24h"] == 0
    assert body["recent_errors"] == []


def test_silent_worker_is_attention_not_a_healthy_desk(client: TestClient) -> None:
    insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    token = login_staff(client, ALEX_EMAIL, ALEX_PASSWORD)
    _set_worker_heartbeat(False)

    response = client.get("/api/status", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["overall"] == "attention"
    assert body["headline"] == "Background work is silent"
    assert body["services"]["worker"] == "silent"
    assert body["services"]["redis"] == "ok"


def test_redis_outage_is_degraded_without_connection_details(
    client: TestClient, monkeypatch
) -> None:
    from app.services import status_service

    class _FailingRedis:
        async def ping(self) -> bool:
            raise RuntimeError("could not connect")

        async def get(self, _key: str) -> None:
            raise RuntimeError("could not connect")

    insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    monkeypatch.setattr(status_service, "get_redis", lambda: _FailingRedis())
    token = login_staff(client, ALEX_EMAIL, ALEX_PASSWORD)

    response = client.get("/api/status", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["overall"] == "degraded"
    assert body["headline"] == "Redis is down"
    assert body["services"]["redis"] == "down"
    assert body["services"]["worker"] == "silent"
    assert "could not connect" not in response.text
    assert "56379" not in response.text
    assert "redis://" not in response.text.lower()


def test_live_counts_are_connected_visitors_and_unique_specialists(client: TestClient) -> None:
    insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    alex_id = insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD)
    token = login_staff(client, ALEX_EMAIL, ALEX_PASSWORD)
    _set_worker_heartbeat(True)
    connection_manager.reset()
    visitor_a = object()
    visitor_b = object()
    tab_one = object()
    tab_two = object()
    connection_manager.register_visitor(
        VisitorConnection(
            websocket=visitor_a,  # type: ignore[arg-type]
            conversation_id=None,
            visitor_id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            parent_origin=HOST_ORIGIN,
        )
    )
    connection_manager.register_visitor(
        VisitorConnection(
            websocket=visitor_b,  # type: ignore[arg-type]
            conversation_id=None,
            visitor_id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            parent_origin=HOST_ORIGIN,
        )
    )
    alex = SimpleNamespace(id=alex_id)
    connection_manager.register_agent(
        AgentConnection(
            websocket=tab_one,  # type: ignore[arg-type]
            user=alex,  # type: ignore[arg-type]
            token_version=0,
            expires_at=NOW + HOUR,
        )
    )
    connection_manager.register_agent(
        AgentConnection(
            websocket=tab_two,  # type: ignore[arg-type]
            user=alex,  # type: ignore[arg-type]
            token_version=0,
            expires_at=NOW + HOUR,
        )
    )
    try:
        response = client.get("/api/status", headers=_auth(token))
    finally:
        connection_manager.reset()

    assert response.status_code == 200
    assert response.json()["live"] == {"visitors": 2, "specialists": 1}
