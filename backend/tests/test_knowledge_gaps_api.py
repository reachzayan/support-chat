"""Suggested-FAQ queue over HTTP.

Oracles: a question appears only after it stumped the bot in 5 different chats within
14 days; ranking is by that chat count; Answer writes a canned reply or a knowledge text
source; Dismiss hides it. Counts below are hand-counted from the seeded rows.
"""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.models.knowledge_gap import KnowledgeGap
from tests.knowledge_gap_fixtures import (
    ANSWER,
    ENROLL,
    NOW,
    PRICING,
    REPORT,
    agent_message,
    auth,
    chats,
    db,
    seed_conversation,
    seed_gap,
    seed_hit,
    world,
)
from tests.ws_helpers import ALEX_PASSWORD, insert_staff


def test_every_route_needs_a_signed_in_staff_member(client: TestClient) -> None:
    """Catches a visitor-facing path reaching the suggested-FAQ queue."""
    gap = str(uuid.uuid4())
    assert client.get("/api/knowledge-gaps").status_code == 401
    assert client.get(f"/api/knowledge-gaps/{gap}/replies").status_code == 401
    assert client.post(f"/api/knowledge-gaps/{gap}/dismiss").status_code == 401
    answer = {"kind": "canned", "shortcut": "x", "body": "y"}
    assert client.post(f"/api/knowledge-gaps/{gap}/answer", json=answer).status_code == 401


def test_a_question_appears_only_after_five_chats_within_fourteen_days(client: TestClient) -> None:
    """Catches one-off or repeated-in-one-chat questions flooding the queue."""
    easy_id, _, staff, _ = world(client)
    seed_gap(
        easy_id,
        ENROLL,
        [
            (ENROLL, 5),
            (ENROLL, 4),
            (ENROLL, 3),
            ("Enrolling a new employee", 1),
            ("how to enroll staff", 2),
        ],
    )
    seed_gap(easy_id, "How do I log in?", chats("How do I log in?", [1, 2, 3, 4]))
    seed_gap(easy_id, "How do I audit?", chats("How do I audit?", [1, 2, 3, 15, 16]))
    seed_gap(easy_id, "Dismissed one", chats("Dismissed one", [1, 2, 3, 4, 5, 6]), "dismissed")
    roster = seed_gap(easy_id, "Update roster?", [])
    with db() as session:
        chat = seed_conversation(session, easy_id)
        for day in (1, 2, 3, 4, 5, 6):
            seed_hit(session, easy_id, roster, "Update roster?", day, chat)

    response = client.get("/api/knowledge-gaps", headers=auth(staff))

    assert response.status_code == 200
    body = response.json()
    assert body["min_conversations"] == 5
    assert body["window_days"] == 14
    assert [item["question"] for item in body["items"]] == [ENROLL]
    item = body["items"][0]
    assert item["site_id"] == str(easy_id)
    assert item["conversations"] == 5
    assert item["examples"] == ["Enrolling a new employee", "how to enroll staff"]
    assert item["last_seen_at"].startswith((NOW - timedelta(days=1)).date().isoformat())


def test_queue_ranks_by_chat_count_and_filters_by_website(client: TestClient) -> None:
    """Catches the hottest question not coming first, or one website seeing another's."""
    easy_id, background_id, staff, _ = world(client)
    seed_gap(easy_id, ENROLL, chats(ENROLL, [1, 2, 3, 4, 5]))
    seed_gap(easy_id, PRICING, chats(PRICING, [1, 2, 3, 4, 5, 6, 7]))
    seed_gap(background_id, REPORT, chats(REPORT, [1, 2, 3, 4, 5, 6]))

    def questions(params: dict[str, str]) -> list[str]:
        response = client.get("/api/knowledge-gaps", params=params, headers=auth(staff))
        assert response.status_code == 200
        return [item["question"] for item in response.json()["items"]]

    assert questions({}) == [PRICING, REPORT, ENROLL]
    assert questions({"site_id": str(easy_id)}) == [PRICING, ENROLL]
    assert questions({"site_id": str(background_id)}) == [REPORT]


def test_replies_show_what_specialists_said_after_the_miss(client: TestClient) -> None:
    """Catches greetings, pre-miss lines, and repeats being offered as the draft answer."""
    easy_id, _, staff, _ = world(client)
    welcome = "Welcome to SampleSite Support, I am Alex, how can I help you today with your account?"
    drivers_tab = "Use the Drivers tab, then press Add driver."
    with db() as session:
        alex = insert_staff("other@example.local", "Other", ALEX_PASSWORD)
        gap = KnowledgeGap(site_id=easy_id, question=ENROLL, status="open")
        session.add(gap)
        session.flush()
        first = seed_conversation(session, easy_id)
        agent_message(session, easy_id, first, alex, welcome)
        seed_hit(session, easy_id, gap.id, ENROLL, 3, first)
        agent_message(session, easy_id, first, alex, "Hi Ada")
        agent_message(session, easy_id, first, alex, ANSWER)
        for days_ago in (2, 1):
            chat = seed_hit(session, easy_id, gap.id, ENROLL, days_ago)
            agent_message(session, easy_id, chat, alex, "Hi")
            agent_message(session, easy_id, chat, alex, drivers_tab)
        seed_hit(session, easy_id, gap.id, ENROLL, 1)
        gap_id = gap.id

    response = client.get(f"/api/knowledge-gaps/{gap_id}/replies", headers=auth(staff))

    assert response.status_code == 200
    assert response.json() == {"items": [drivers_tab, ANSWER]}


def test_dismiss_hides_the_question_and_cannot_be_repeated(client: TestClient) -> None:
    """Catches a dismissed question coming back, or a double click erroring silently."""
    easy_id, _, staff, _ = world(client)
    gap_id = seed_gap(easy_id, ENROLL, chats(ENROLL, [1, 2, 3, 4, 5]))

    first = client.post(f"/api/knowledge-gaps/{gap_id}/dismiss", headers=auth(staff))
    again = client.post(f"/api/knowledge-gaps/{gap_id}/dismiss", headers=auth(staff))
    listed = client.get("/api/knowledge-gaps", headers=auth(staff))

    assert first.status_code == 204
    assert again.status_code == 409
    assert listed.json()["items"] == []


def test_unknown_gap_is_not_found(client: TestClient) -> None:
    """Catches a guessed id reaching another website's data or crashing."""
    _, _, staff, _ = world(client)
    missing = uuid.uuid4()
    assert (
        client.post(f"/api/knowledge-gaps/{missing}/dismiss", headers=auth(staff)).status_code
        == 404
    )
    assert (
        client.get(f"/api/knowledge-gaps/{missing}/replies", headers=auth(staff)).status_code == 404
    )


def test_answering_with_a_canned_reply_creates_a_bot_ready_reply(client: TestClient) -> None:
    """Catches Answer closing the question without writing the reply the bot will use."""
    easy_id, _, staff, _ = world(client)
    gap_id = seed_gap(easy_id, ENROLL, chats(ENROLL, [1, 2, 3, 4, 5]))

    answered = client.post(
        f"/api/knowledge-gaps/{gap_id}/answer",
        headers=auth(staff),
        json={"kind": "canned", "shortcut": "enrollment", "body": ANSWER},
    )
    library = client.get("/api/canned-replies/library", headers=auth(staff)).json()["items"]
    listed = client.get("/api/knowledge-gaps", headers=auth(staff)).json()["items"]

    assert answered.status_code == 204
    assert [
        (row["site_id"], row["shortcut"], row["body"], row["enabled"], row["bot_eligible"])
        for row in library
    ] == [(str(easy_id), "enrollment", ANSWER, True, True)]
    assert listed == []


def test_a_taken_shortcut_keeps_the_question_open(client: TestClient) -> None:
    """Catches a failed save silently closing a question nobody answered."""
    easy_id, _, staff, _ = world(client)
    gap_id = seed_gap(easy_id, ENROLL, chats(ENROLL, [1, 2, 3, 4, 5]))
    taken = client.post(
        "/api/canned-replies",
        headers=auth(staff),
        json={"site_id": str(easy_id), "shortcut": "enrollment", "body": "Already here."},
    )
    assert taken.status_code == 201

    answered = client.post(
        f"/api/knowledge-gaps/{gap_id}/answer",
        headers=auth(staff),
        json={"kind": "canned", "shortcut": "enrollment", "body": ANSWER},
    )
    listed = client.get("/api/knowledge-gaps", headers=auth(staff)).json()["items"]

    assert answered.status_code == 409
    assert [item["question"] for item in listed] == [ENROLL]


def test_knowledge_answer_needs_an_admin_and_creates_a_text_source(client: TestClient) -> None:
    """Catches non-admin staff writing to the knowledge base, or Answer skipping the source."""
    easy_id, _, staff, admin = world(client)
    gap_id = seed_gap(easy_id, ENROLL, chats(ENROLL, [1, 2, 3, 4, 5]))
    payload = {"kind": "knowledge", "title": "Enrollment process", "body": ANSWER}

    denied = client.post(f"/api/knowledge-gaps/{gap_id}/answer", headers=auth(staff), json=payload)
    still_open = client.get("/api/knowledge-gaps", headers=auth(staff)).json()["items"]
    allowed = client.post(f"/api/knowledge-gaps/{gap_id}/answer", headers=auth(admin), json=payload)
    sources = client.get(f"/api/sites/{easy_id}/kb-sources", headers=auth(admin)).json()["items"]
    closed = client.get("/api/knowledge-gaps", headers=auth(staff)).json()["items"]

    assert denied.status_code == 403
    assert [item["question"] for item in still_open] == [ENROLL]
    assert allowed.status_code == 204
    assert [(row["source_kind"], row["display_name"]) for row in sources] == [
        ("text", "Enrollment process")
    ]
    assert closed == []
