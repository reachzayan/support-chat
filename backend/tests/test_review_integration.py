"""API/socket regressions against real Postgres and Redis; no model calls."""

import csv
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.refresh_token import RefreshToken
from app.models.site import Site
from app.models.visitor import Visitor
from scripts.purge_expired_chats import purge_expired
from tests.ws_helpers import (
    STAFF_ORIGIN,
    WIDGET_ORIGIN,
    auth_agent,
    auth_visitor,
    collect_until,
    decode_widget_token,
    login_staff,
    post_bootstrap,
    seed_demo_world,
    sync_session,
)


def _submitted_chat(client):
    site_id, _ = seed_demo_world()
    token = post_bootstrap(client).json()["bootstrap_token"]
    visitor_id = UUID(decode_widget_token(token)["visitor_id"])
    for session in sync_session():
        visitor = session.get(Visitor, visitor_id)
        visitor.name = "=1+2"
        visitor.email = "review@example.com"
        conversation = Conversation(
            site_id=site_id,
            visitor_id=visitor_id,
            state="queued",
            prechat_submission_id=uuid4(),
            prechat_payload_hash="review",
        )
        session.add(conversation)
        session.commit()
        conversation_id = conversation.id
    return site_id, conversation_id, token


def test_disabled_site_rejects_previously_issued_socket_token(client):
    site_id, _, token = _submitted_chat(client)
    for session in sync_session():
        session.get(Site, site_id).enabled = False
        session.commit()
    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as socket:
        auth_visitor(socket, token)
        with pytest.raises(WebSocketDisconnect) as rejected:
            socket.receive_json()
        assert rejected.value.code == 4403


@pytest.mark.parametrize("peer", ["visitor", "agent"])
def test_normal_ping_recovers_a_committed_message_without_a_wakeup(client, peer):
    site_id, conversation_id, token = _submitted_chat(client)
    access = login_staff(client)
    origin = WIDGET_ORIGIN if peer == "visitor" else STAFF_ORIGIN
    with client.websocket_connect(f"/ws/{peer}", headers={"Origin": origin}) as socket:
        if peer == "visitor":
            auth_visitor(socket, token)
        else:
            auth_agent(socket, access)
            socket.send_json({"v": 1, "type": "subscribe", "conversation_id": str(conversation_id)})
        collect_until(socket, lambda frames: any(f.get("type") == "state" for f in frames))
        # This row is committed without publishing any notification, as after a process crash.
        for session in sync_session():
            session.add(
                Message(
                    conversation_id=conversation_id,
                    site_id=site_id,
                    role="system",
                    body="Committed while notification was unavailable.",
                )
            )
            session.commit()
        socket.send_json({"v": 1, "type": "ping"})
        socket.send_json({"v": 1, "type": "review_barrier"})
        frames = collect_until(socket, lambda frames: any(f.get("type") == "error" for f in frames))
        assert [f["body"] for f in frames if f.get("type") == "message"] == [
            "Committed while notification was unavailable."
        ]


def test_export_neutralizes_visitor_formula_cells(client):
    _submitted_chat(client)
    access = login_staff(client)
    response = client.post(
        "/api/conversations/submissions/export",
        headers={"Authorization": f"Bearer {access}"},
        json={"columns": ["Name", "Email"]},
    )
    assert response.status_code == 200
    assert list(csv.reader(StringIO(response.text))) == [
        ["Name", "Email"],
        ["'=1+2", "review@example.com"],
    ]


def test_rejected_refresh_removes_both_browser_cookies(client):
    seed_demo_world()
    login_staff(client)
    csrf = client.cookies.get("supportchat_csrf")
    for session in sync_session():
        row = session.scalar(select(RefreshToken))
        session.delete(row)
        session.commit()
    response = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 401
    assert client.cookies.get("supportchat_refresh") is None
    assert client.cookies.get("supportchat_csrf") is None


def test_retention_preserves_an_open_prechat_identity(client):
    site_id, _ = seed_demo_world()
    token = post_bootstrap(client).json()["bootstrap_token"]
    visitor_id = UUID(decode_widget_token(token)["visitor_id"])
    for session in sync_session():
        stale = Visitor(
            site_id=site_id,
            resume_token_hash="stale-unsubmitted-identity",
            created_at=datetime.now(UTC) - timedelta(days=31),
        )
        session.add(stale)
        session.commit()
        stale_id = stale.id
    counts = client.portal.call(purge_expired)
    assert counts == {"conversations": 0, "visitors": 1}
    for session in sync_session():
        assert session.get(Visitor, visitor_id) is not None
        assert session.get(Visitor, stale_id) is None


@pytest.mark.parametrize("peer", ["visitor", "agent"])
def test_socket_rejects_non_string_frame_type_without_disconnecting(client, peer):
    _, conversation_id, token = _submitted_chat(client)
    access = login_staff(client)
    origin = WIDGET_ORIGIN if peer == "visitor" else STAFF_ORIGIN
    with client.websocket_connect(f"/ws/{peer}", headers={"Origin": origin}) as socket:
        if peer == "visitor":
            auth_visitor(socket, token)
        else:
            auth_agent(socket, access)
            socket.send_json({"v": 1, "type": "subscribe", "conversation_id": str(conversation_id)})
        collect_until(socket, lambda frames: any(f.get("type") == "state" for f in frames))
        socket.send_json({"v": 1, "type": []})
        frames = collect_until(socket, lambda frames: any(f.get("type") == "error" for f in frames))
        assert frames[-1]["code"] == "invalid"
        socket.send_json({"v": 1, "type": "ping"})
        collect_until(socket, lambda frames: any(f.get("type") == "pong" for f in frames))


def test_unsubscribe_stops_heartbeat_replay(client):
    site_id, conversation_id, _ = _submitted_chat(client)
    access = login_staff(client)
    with client.websocket_connect("/ws/agent", headers={"Origin": STAFF_ORIGIN}) as socket:
        auth_agent(socket, access)
        socket.send_json({"v": 1, "type": "subscribe", "conversation_id": str(conversation_id)})
        collect_until(socket, lambda frames: any(f.get("type") == "state" for f in frames))
        socket.send_json({"v": 1, "type": "unsubscribe", "conversation_id": str(conversation_id)})
        socket.send_json({"v": 1, "type": "review_barrier"})
        collect_until(socket, lambda frames: any(f.get("type") == "error" for f in frames))
        for session in sync_session():
            session.add(
                Message(
                    conversation_id=conversation_id,
                    site_id=site_id,
                    role="system",
                    body="After unsubscribe",
                )
            )
            session.commit()
        socket.send_json({"v": 1, "type": "ping"})
        socket.send_json({"v": 1, "type": "review_barrier"})
        frames = collect_until(socket, lambda frames: any(f.get("type") == "error" for f in frames))
        assert not any(f.get("type") in {"message", "state"} for f in frames)


def test_export_rejects_excess_rows_instead_of_silently_truncating(client):
    from sqlalchemy import insert

    site_id, conversation_id, _ = _submitted_chat(client)
    access = login_staff(client)
    for session in sync_session():
        visitor_id = session.get(Conversation, conversation_id).visitor_id
        session.execute(
            insert(Conversation),
            [
                {
                    "site_id": site_id,
                    "visitor_id": visitor_id,
                    "state": "closed",
                    "prechat_submission_id": uuid4(),
                    "prechat_payload_hash": "review",
                }
                for _ in range(10_000)
            ],
        )
        session.commit()
    response = client.post(
        "/api/conversations/submissions/export",
        headers={"Authorization": f"Bearer {access}"},
        json={"columns": ["Name"]},
    )
    assert response.status_code == 422
    assert (
        response.json()["detail"] == "Export exceeds 10,000 rows. Narrow the site or date filters."
    )


def test_http_transcript_preserves_citation_metadata(client):
    site_id, conversation_id, _ = _submitted_chat(client)
    access = login_staff(client)
    for session in sync_session():
        session.add(
            Message(
                conversation_id=conversation_id,
                site_id=site_id,
                role="bot",
                body="An answer.",
                source_urls=["https://sample-site.example.com/faq"],
                source_title="Screening FAQ",
            )
        )
        session.commit()
    response = client.get(
        f"/api/conversations/{conversation_id}", headers={"Authorization": f"Bearer {access}"}
    )
    assert response.status_code == 200
    assert response.json()["messages"][0]["citations"] == [
        {
            "source_url": "https://sample-site.example.com/faq",
            "source_title": "Screening FAQ",
            "cited_text": None,
        }
    ]


def test_competing_faq_answers_create_only_one_reply(client):
    from concurrent.futures import ThreadPoolExecutor

    from app.models.canned_reply import CannedReply
    from app.models.knowledge_gap import KnowledgeGap

    site_id, _ = seed_demo_world()
    access = login_staff(client)
    with next(sync_session()) as session:
        gap = KnowledgeGap(site_id=site_id, question="Where do I enroll?", status="open")
        session.add(gap)
        session.commit()
        gap_id = gap.id

    def answer(shortcut):
        return client.post(
            f"/api/knowledge-gaps/{gap_id}/answer",
            headers={"Authorization": f"Bearer {access}"},
            json={"kind": "canned", "shortcut": shortcut, "body": "Enroll in the portal."},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(answer, ["enroll-a", "enroll-b"]))
    assert sorted(results) == [204, 409]
    for session in sync_session():
        assert len(list(session.scalars(select(CannedReply)))) == 1
        assert session.get(KnowledgeGap, gap_id).status == "canned"


def test_identical_embedding_is_a_perfect_canned_match(client):
    from app.db import session_maker
    from app.models.canned_reply import CannedReply
    from app.services.canned_bot import search_canned
    from app.services.kb_embedder import FakeEmbedder

    site_id, _ = seed_demo_world()

    async def search():
        embedder = FakeEmbedder()
        vector = await embedder.embed_query("enrollment")
        async with session_maker()() as session:
            session.add(
                CannedReply(
                    site_id=site_id,
                    shortcut="enrollment",
                    body="Enroll in the portal.",
                    bot_eligible=True,
                    enabled=True,
                    embedding=vector,
                    embedder_id=embedder.embedder_id,
                )
            )
            await session.commit()
            return await search_canned(session, embedder, site_id, "enrollment")

    hits = client.portal.call(search)
    assert len(hits) == 1
    assert hits[0].cosine == 1.0
