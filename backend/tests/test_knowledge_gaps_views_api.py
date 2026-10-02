"""Suggested-FAQ queue: spike trigger, Answered/Dismissed views, website note, closest
existing entry, and the inbox badge.

Oracles: a burst of 3 different chats within 24 hours surfaces a question before the 5-in-14-days
rule would; Dismissed and Answered keep their all-time counts and can be reopened; a gap's
closest canned reply / knowledge entry is the one on the same website (or General) with cosine
>= 0.55, using hand-computed 2-D vectors (cos 0.9, 0.8 and 0.0).
"""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.knowledge_gaps import get_embedder
from app.models.canned_reply import CannedReply
from app.models.knowledge_gap import KnowledgeGapHit
from tests.knowledge_gap_fixtures import (
    ENROLL,
    NOW,
    PRICING,
    REPORT,
    auth,
    chats,
    db,
    seed_chunk,
    seed_conversation,
    seed_gap,
    seed_hit,
    world,
)

HOUR = timedelta(hours=1)
VECTOR_SIZE = 1536


def _vector(x: float, y: float) -> list[float]:
    return [x, y] + [0.0] * (VECTOR_SIZE - 2)


QUESTION_VECTOR = _vector(1.0, 0.0)
CLOSE = _vector(0.9, 0.4359)  # cos with QUESTION_VECTOR = 0.9
CLOSER_THAN_FLOOR = _vector(0.8, 0.6)  # 0.8
UNRELATED = _vector(0.0, 1.0)  # 0.0


class StubEmbedder:
    embedder_id = "stub:test"
    dim = VECTOR_SIZE

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [QUESTION_VECTOR for _ in texts]

    async def embed_query(self, text: str) -> list[float] | None:
        return QUESTION_VECTOR


@pytest.fixture
def stub_embedder(client: TestClient):
    client.app.dependency_overrides[get_embedder] = StubEmbedder
    yield
    client.app.dependency_overrides.pop(get_embedder, None)


def _canned_with_vector(session, site_id, shortcut: str, vector: list[float]) -> CannedReply:
    row = CannedReply(
        site_id=site_id,
        shortcut=shortcut,
        body=f"Body of {shortcut}.",
        embedding=vector,
        embedder_id="stub:test",
    )
    session.add(row)
    session.flush()
    return row


def _items(client: TestClient, token: str, **params: str) -> list[dict]:
    response = client.get("/api/knowledge-gaps", params=params, headers=auth(token))
    assert response.status_code == 200
    return response.json()["items"]


def test_a_burst_of_chats_surfaces_a_question_before_the_five_chat_rule(
    client: TestClient,
) -> None:
    """Catches a question that just started repeating waiting two weeks to be noticed."""
    easy_id, _, staff, _ = world(client)
    seed_gap(easy_id, PRICING, chats(PRICING, [HOUR, 2 * HOUR, 3 * HOUR]))
    seed_gap(easy_id, "Calm question?", chats("Calm question?", [HOUR, 2 * HOUR]))
    seed_gap(easy_id, ENROLL, chats(ENROLL, [2, 3, 4, 5, 6, 7]))
    one_chat = seed_gap(easy_id, "Loud but single?", [])
    with db() as session:
        chat = seed_conversation(session, easy_id)
        for hours in (1, 2, 3, 4):
            seed_hit(session, easy_id, one_chat, "Loud but single?", hours * HOUR, chat)

    response = client.get("/api/knowledge-gaps", headers=auth(staff))

    body = response.json()
    assert [(i["question"], i["conversations"], i["spiking"]) for i in body["items"]] == [
        (PRICING, 3, True),
        (ENROLL, 6, False),
    ]
    assert (body["spike_conversations"], body["spike_hours"]) == (3, 24)


def test_dismissed_and_answered_questions_have_their_own_views_and_can_be_reopened(
    client: TestClient,
) -> None:
    """Catches a mistaken Dismiss being permanent, or history losing its all-time counts."""
    easy_id, _, staff, _ = world(client)
    dismissed = seed_gap(
        easy_id,
        ENROLL,
        chats(ENROLL, [1, 2, 3, 4, 5]),
        status="dismissed",
        resolved_at=NOW - timedelta(days=1),
    )
    seed_gap(easy_id, PRICING, chats(PRICING, [3, 40]), status="canned", resolved_at=NOW)
    seed_gap(easy_id, REPORT, chats(REPORT, [1, 2, 3, 4, 5, 6]))

    def view(status: str) -> list[tuple[str, int, str]]:
        return [
            (item["question"], item["conversations"], item["status"])
            for item in _items(client, staff, status=status)
        ]

    assert view("open") == [(REPORT, 6, "open")]
    assert view("dismissed") == [(ENROLL, 5, "dismissed")]
    assert view("answered") == [(PRICING, 2, "canned")]

    reopened = client.post(f"/api/knowledge-gaps/{dismissed}/reopen", headers=auth(staff))
    again = client.post(f"/api/knowledge-gaps/{dismissed}/reopen", headers=auth(staff))
    missing = client.post(f"/api/knowledge-gaps/{uuid.uuid4()}/reopen", headers=auth(staff))

    assert reopened.status_code == 204
    assert again.status_code == 409
    assert missing.status_code == 404
    assert view("open") == [(REPORT, 6, "open"), (ENROLL, 5, "open")]
    assert view("dismissed") == []


def test_a_note_for_the_website_team_is_trimmed_cleared_and_kept_in_every_view(
    client: TestClient,
) -> None:
    """Catches the 'site needs a Get started section' flag being lost or shown untrimmed."""
    easy_id, _, staff, _ = world(client)
    gap_id = seed_gap(easy_id, ENROLL, chats(ENROLL, [1, 2, 3, 4, 5]))
    url = f"/api/knowledge-gaps/{gap_id}"

    saved = client.patch(
        url, headers=auth(staff), json={"note": "  Site needs a Get started page.  "}
    )
    noted = _items(client, staff)[0]["note"]
    dismissed = client.post(f"{url}/dismiss", headers=auth(staff))
    kept = _items(client, staff, status="dismissed")[0]["note"]
    cleared = client.patch(url, headers=auth(staff), json={"note": "   "})
    empty = _items(client, staff, status="dismissed")[0]["note"]
    too_long = client.patch(url, headers=auth(staff), json={"note": "x" * 1001})
    missing = client.patch(
        f"/api/knowledge-gaps/{uuid.uuid4()}", headers=auth(staff), json={"note": "x"}
    )
    anonymous = client.patch(url, json={"note": "x"})

    assert (saved.status_code, dismissed.status_code, cleared.status_code) == (204, 204, 204)
    assert noted == "Site needs a Get started page."
    assert kept == "Site needs a Get started page."
    assert empty is None
    assert (too_long.status_code, missing.status_code, anonymous.status_code) == (422, 404, 401)


def test_the_closest_canned_reply_is_on_this_website_or_general_and_above_the_floor(
    client: TestClient, stub_embedder: None
) -> None:
    """Catches a second 'enrollment' reply being created next to a close one, or a leak."""
    easy_id, background_id, staff, _ = world(client)
    gap_id = seed_gap(easy_id, ENROLL, chats(ENROLL, [1, 2, 3, 4, 5]))

    with db() as session:
        close = _canned_with_vector(session, easy_id, "enrollment_process", CLOSE)
        _canned_with_vector(session, easy_id, "pricing", UNRELATED)
        _canned_with_vector(session, background_id, "other_site_exact", QUESTION_VECTOR)
        general = _canned_with_vector(session, None, "general_enroll", CLOSER_THAN_FLOOR)
        close_id, general_id = str(close.id), str(general.id)

    first = client.get(f"/api/knowledge-gaps/{gap_id}/similar", headers=auth(staff)).json()
    with db() as session:
        session.delete(session.get(CannedReply, uuid.UUID(close_id)))
    second = client.get(f"/api/knowledge-gaps/{gap_id}/similar", headers=auth(staff)).json()

    assert first["canned"] == {
        "id": close_id,
        "site_id": str(easy_id),
        "shortcut": "enrollment_process",
        "excerpt": "Body of enrollment_process.",
        "enabled": True,
        "bot_eligible": True,
        "similarity": 0.9,
    }
    assert second["canned"]["id"] == general_id
    assert second["canned"]["site_id"] is None
    assert second["canned"]["similarity"] == 0.8


def test_nothing_is_suggested_when_no_existing_entry_is_close(
    client: TestClient, stub_embedder: None
) -> None:
    """Catches the dialog nagging staff to edit an unrelated reply."""
    easy_id, _, staff, _ = world(client)
    gap_id = seed_gap(easy_id, ENROLL, chats(ENROLL, [1, 2, 3, 4, 5]))
    with db() as session:
        session.add(
            CannedReply(
                site_id=easy_id,
                shortcut="pricing",
                body="Prices.",
                embedding=UNRELATED,
                embedder_id="stub:test",
            )
        )

    response = client.get(f"/api/knowledge-gaps/{gap_id}/similar", headers=auth(staff))

    assert response.json() == {"canned": None, "knowledge": None}


def test_the_closest_knowledge_entry_is_this_websites_page(
    client: TestClient, stub_embedder: None
) -> None:
    """Catches a bad webpage chunk being left in place while a duplicate article is added."""
    easy_id, background_id, staff, _ = world(client)
    gap_id = seed_gap(easy_id, ENROLL, chats(ENROLL, [1, 2, 3, 4, 5]))
    with db() as session:
        seed_chunk(
            session,
            easy_id,
            "Recruiter steps after enrollment",
            "Recruiters review candidates after enrollment.",
            CLOSE,
        )
        seed_chunk(session, easy_id, "Unrelated pricing page", "Prices vary.", UNRELATED)
        seed_chunk(
            session, background_id, "Other website page", "Other website content.", QUESTION_VECTOR
        )

    knowledge = client.get(f"/api/knowledge-gaps/{gap_id}/similar", headers=auth(staff)).json()[
        "knowledge"
    ]

    assert knowledge["title"] == "Recruiter steps after enrollment"
    assert knowledge["url"].startswith("https://legacy.test/")
    assert knowledge["similarity"] == 0.9


def test_a_chat_in_a_listed_question_reports_it_for_the_inbox_badge(client: TestClient) -> None:
    """Catches agents not seeing that the visitor in front of them is part of a repeat."""
    easy_id, _, staff, _ = world(client)
    hot = seed_gap(easy_id, ENROLL, chats(ENROLL, [1, 2, 3, 4, 5]))
    below = seed_gap(easy_id, PRICING, chats(PRICING, [1, 2, 3, 4]))
    dismissed = seed_gap(easy_id, REPORT, chats(REPORT, [1, 2, 3, 4, 5]), status="dismissed")

    def a_chat(gap_id: uuid.UUID) -> uuid.UUID:
        with db() as session:
            return session.scalars(
                select(KnowledgeGapHit.conversation_id).where(KnowledgeGapHit.gap_id == gap_id)
            ).first()

    def badge(conversation_id: uuid.UUID) -> dict:
        response = client.get(
            f"/api/conversations/{conversation_id}/knowledge-gap", headers=auth(staff)
        )
        assert response.status_code == 200
        return response.json()

    assert badge(a_chat(hot)) == {
        "gap": {"id": str(hot), "question": ENROLL, "conversations": 5, "spiking": False}
    }
    assert badge(a_chat(below)) == {"gap": None}
    assert badge(a_chat(dismissed)) == {"gap": None}
    assert badge(uuid.uuid4()) == {"gap": None}
    assert client.get(f"/api/conversations/{a_chat(hot)}/knowledge-gap").status_code == 401
