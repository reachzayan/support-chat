import asyncio
import time
import uuid
from concurrent.futures import CancelledError, ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.chat.outcome_copy import keep_helping_line
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.visitor import Visitor
from tests.ws_helpers import (
    AGENT_HELP,
    AGENT_MESSAGE_ID,
    ALEX_NAME,
    DEMO_NAME,
    DEMO_PUBLIC_KEY,
    DEMO_SITE_KEY,
    DOT_QUESTION,
    HOST_ORIGIN,
    JOIN_LINE_ALEX,
    JORDAN_EMAIL,
    JORDAN_NAME,
    JORDAN_PASSWORD,
    PRECHAT_SUBMISSION_ID,
    STAFF_ORIGIN,
    STILL_THERE,
    VISITOR_MESSAGE_ID,
    WIDGET_ORIGIN,
    assigned_agent_id,
    auth_agent,
    auth_visitor,
    bot_row_count,
    collect_until,
    conversation_count,
    conversation_id_from_state,
    conversation_state,
    decode_widget_token,
    frames_of_type,
    insert_staff,
    login_staff,
    message_count,
    open_conversations_for_visitor,
    page_fields,
    post_bootstrap,
    seed_demo_world,
    sync_session,
    visitor_contact,
    visitor_count,
)


def _boot(client: TestClient) -> dict:
    seed_demo_world()
    response = post_bootstrap(client)
    assert response.status_code == 200
    body = response.json()
    claims = decode_widget_token(body["bootstrap_token"])
    return {
        "bootstrap_token": body["bootstrap_token"],
        "resume_token": body["resume_token"],
        "visitor_id": claims["visitor_id"],
        "access_token": login_staff(client),
    }


def _delay_bot_turn(monkeypatch: pytest.MonkeyPatch, seconds: float = 0.5) -> None:
    """Hold the bot long enough for an agent Join to clear the generation lease."""
    from app.services.conversation_service import ConversationService

    original = ConversationService.run_bot_turn

    async def slow(self, conversation_id, generation_id, **kwargs):
        await asyncio.sleep(seconds)
        return await original(self, conversation_id, generation_id, **kwargs)

    monkeypatch.setattr(ConversationService, "run_bot_turn", slow)


def test_widget_bootstrap_and_socket_page_older_messages(client: TestClient) -> None:
    ctx = _boot(client)
    visitor_id = uuid.UUID(ctx["visitor_id"])
    session = next(sync_session())
    try:
        visitor = session.get(Visitor, visitor_id)
        assert visitor is not None
        conversation = Conversation(
            site_id=visitor.site_id,
            visitor_id=visitor.id,
            state="bot",
            prechat_submission_id=uuid.uuid4(),
            prechat_payload_hash="a" * 64,
        )
        session.add(conversation)
        session.flush()
        conversation_id = conversation.id
        session.add_all(
            Message(
                conversation_id=conversation_id,
                site_id=conversation.site_id,
                role="system",
                body=f"note {index}",
            )
            for index in range(55)
        )
        session.commit()
    finally:
        session.close()

    response = post_bootstrap(
        client,
        {
            "site_key": DEMO_SITE_KEY,
            "public_key": DEMO_PUBLIC_KEY,
            "resume_token": ctx["resume_token"],
            "action": "open",
            "conversation_id": str(conversation_id),
        },
    )
    assert response.status_code == 200
    snapshot = response.json()["conversation"]
    assert snapshot["has_older"] is True
    assert len(snapshot["messages"]) == 50
    assert snapshot["messages"][0]["body"] == "note 5"
    assert snapshot["messages"][-1]["body"] == "note 54"

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        visitor.send_json(
            {
                "v": 1,
                "type": "auth",
                "bootstrap_token": response.json()["bootstrap_token"],
                "parent_origin": STAFF_ORIGIN,
                "last_event_id": snapshot["messages"][-1]["id"],
            }
        )
        assert visitor.receive_json()["type"] == "state"
        visitor.send_json({"v": 1, "type": "older", "before_id": snapshot["messages"][0]["id"]})
        page = visitor.receive_json()
        assert page["type"] == "history_page"
        assert [message["body"] for message in page["messages"]] == [
            f"note {index}" for index in range(5)
        ]
        assert page["has_older"] is False


def test_prechat_dot_question_reaches_subscribed_agent_once_and_agent_reply_is_canonical(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _delay_bot_turn(monkeypatch)
    ctx = _boot(client)

    with client.websocket_connect("/ws/agent", headers={"Origin": STAFF_ORIGIN}) as agent:
        auth_agent(agent, ctx["access_token"])
        with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
            auth_visitor(visitor, ctx["bootstrap_token"])
            collect_until(
                visitor, lambda frames: any(frame.get("type") == "state" for frame in frames)
            )
            visitor.send_json(
                {
                    "v": 1,
                    "type": "prechat",
                    "submission_id": PRECHAT_SUBMISSION_ID,
                    "name": "Ada Lopez",
                    "email": "ada@example.com",
                    "phone": "",
                    "inquiry_type": "results",
                    "message": DOT_QUESTION,
                }
            )
            accepted = collect_until(
                visitor,
                lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
            )
            conversation_id = conversation_id_from_state(accepted)
            prechat = frames_of_type(accepted, "prechat_accepted")[-1]
            assert prechat["submission_id"] == PRECHAT_SUBMISSION_ID
            assert prechat["message_id"] is not None
            agent.send_json(
                {
                    "v": 1,
                    "type": "subscribe",
                    "conversation_id": conversation_id,
                    "last_event_id": 0,
                }
            )

            agent.send_json({"v": 1, "type": "join", "conversation_id": conversation_id})
            collect_until(
                visitor,
                lambda frames: any(
                    frame.get("type") == "message" and frame.get("body") == JOIN_LINE_ALEX
                    for frame in frames
                ),
            )
            agent_frames = collect_until(
                agent,
                lambda frames: any(
                    frame.get("type") == "message" and frame.get("body") == DOT_QUESTION
                    for frame in frames
                ),
            )
            visitor_rows = [
                frame
                for frame in agent_frames
                if frame.get("type") == "message" and frame.get("body") == DOT_QUESTION
            ]
            assert len(visitor_rows) == 1
            assert visitor_rows[0]["role"] == "visitor"
            assert visitor_rows[0]["id"] == prechat["message_id"]
            agent.send_json(
                {
                    "v": 1,
                    "type": "message",
                    "conversation_id": conversation_id,
                    "client_message_id": AGENT_MESSAGE_ID,
                    "body": AGENT_HELP,
                }
            )
            both = collect_until(
                visitor,
                lambda frames: any(
                    frame.get("type") == "message" and frame.get("body") == AGENT_HELP
                    for frame in frames
                ),
            )
            agent_seen = collect_until(
                agent,
                lambda frames: any(
                    frame.get("type") == "message" and frame.get("body") == AGENT_HELP
                    for frame in frames
                ),
            )

    help_on_visitor = [
        frame
        for frame in both
        if frame.get("type") == "message" and frame.get("body") == AGENT_HELP
    ]
    help_on_agent = [
        frame
        for frame in agent_seen
        if frame.get("type") == "message" and frame.get("body") == AGENT_HELP
    ]
    assert len(help_on_visitor) == 1
    assert len(help_on_agent) == 1
    assert help_on_visitor[0]["role"] == "agent"
    assert help_on_visitor[0]["id"] == help_on_agent[0]["id"]
    assert message_count(uuid.UUID(conversation_id), role="visitor", body=DOT_QUESTION) == 1
    assert message_count(uuid.UUID(conversation_id), role="agent", body=AGENT_HELP) == 1
    assert bot_row_count() == 0
    assert visitor_contact(uuid.UUID(ctx["visitor_id"])) == ("Ada Lopez", "ada@example.com", None)


def test_duplicate_client_ids_ack_once_and_conflict_on_payload_change(
    client: TestClient,
) -> None:
    ctx = _boot(client)
    empty_submission = "10000000-0000-4000-8000-000000000099"

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, ctx["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": empty_submission,
                "name": "Ada Lopez",
                "email": "ada@example.com",
                "phone": "",
                "inquiry_type": "other",
                "message": "",
            }
        )
        empty_frames = collect_until(
            visitor,
            lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
        )
        conversation_id = uuid.UUID(conversation_id_from_state(empty_frames))
        empty_ack = frames_of_type(empty_frames, "prechat_accepted")[-1]
        assert empty_ack["message_id"] is None
        assert message_count(conversation_id, role="visitor") == 0
        assert (
            message_count(
                conversation_id,
                role="system",
                body="Hi, welcome to SupportChat demo. How can we help you today?",
            )
            == 1
        )
        assert conversation_state(conversation_id) == "bot"

        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": empty_submission,
                "name": "Ada Lopez",
                "email": "ada@example.com",
                "phone": "",
                "inquiry_type": "other",
                "message": "",
            }
        )
        retry_frames = collect_until(
            visitor,
            lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
        )
        assert frames_of_type(retry_frames, "prechat_accepted")[-1]["message_id"] is None
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": empty_submission,
                "name": "Ada Lopez",
                "email": "other@example.com",
                "phone": "",
                "inquiry_type": "other",
                "message": "",
            }
        )
        conflict_prechat = collect_until(
            visitor,
            lambda frames: any(
                frame.get("type") == "error" and frame.get("code") == "idempotency_conflict"
                for frame in frames
            ),
        )
        assert frames_of_type(conflict_prechat, "error")[-1]["code"] == "idempotency_conflict"
        assert visitor_contact(uuid.UUID(ctx["visitor_id"])) == (
            "Ada Lopez",
            "ada@example.com",
            None,
        )
        assert conversation_state(conversation_id) == "bot"
        assert message_count(conversation_id, role="visitor") == 0
        assert (
            message_count(
                conversation_id,
                role="system",
                body="Hi, welcome to SupportChat demo. How can we help you today?",
            )
            == 1
        )

        visitor.send_json(
            {
                "v": 1,
                "type": "message",
                "client_message_id": VISITOR_MESSAGE_ID,
                "body": STILL_THERE,
            }
        )
        first = collect_until(
            visitor, lambda frames: any(frame.get("type") == "ack" for frame in frames)
        )
        first_ack = frames_of_type(first, "ack")[-1]
        collect_until(
            visitor,
            lambda frames: any(
                frame.get("type") == "typing" and frame.get("active") is False for frame in frames
            ),
        )
        visitor.send_json(
            {
                "v": 1,
                "type": "message",
                "client_message_id": VISITOR_MESSAGE_ID,
                "body": STILL_THERE,
            }
        )
        second = collect_until(
            visitor, lambda frames: any(frame.get("type") == "ack" for frame in frames)
        )
        second_ack = frames_of_type(second, "ack")[-1]
        assert first_ack["id"] == second_ack["id"]
        assert first_ack["client_message_id"] == VISITOR_MESSAGE_ID
        visitor.send_json(
            {
                "v": 1,
                "type": "message",
                "client_message_id": VISITOR_MESSAGE_ID,
                "body": "different body",
            }
        )
        conflict = collect_until(
            visitor,
            lambda frames: any(
                frame.get("type") == "error" and frame.get("code") == "idempotency_conflict"
                for frame in frames
            ),
        )
        assert frames_of_type(conflict, "error")[-1]["code"] == "idempotency_conflict"

    assert message_count(conversation_id, role="visitor") == 1
    assert message_count(conversation_id, body=STILL_THERE) == 1
    assert message_count(conversation_id, body="different body") == 0
    # Idempotent ack must not create a second visitor row; a single bot reply is fine.
    assert message_count(conversation_id, role="visitor") == 1


def test_visitor_escalate_frame_stays_with_the_bot(
    client: TestClient,
) -> None:
    ctx = _boot(client)
    keep_helping = keep_helping_line(DEMO_NAME)
    offered: list[dict] = []

    # Starlette's TestClient portal can CancelledError on close after fanout;
    # keep assertions outside so a cleanup race cannot hide the product check.
    socket = client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN})
    visitor = socket.__enter__()
    try:
        auth_visitor(visitor, ctx["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": "10000000-0000-4000-8000-000000000098",
                "name": "Ada Lopez",
                "email": "ada@example.com",
                "phone": "",
                "inquiry_type": "other",
                "message": "",
            }
        )
        started = collect_until(
            visitor,
            lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
        )
        conversation_id = uuid.UUID(conversation_id_from_state(started))

        visitor.send_json({"v": 1, "type": "escalate"})
        visitor.send_json({"v": 1, "type": "heartbeat"})
        offered = collect_until(
            visitor,
            lambda frames: any(
                frame.get("type") == "message" and frame.get("body") == keep_helping
                for frame in frames
            ),
        )
        assert all(frame.get("state") != "queued" for frame in frames_of_type(offered, "state"))
    finally:
        try:
            socket.__exit__(None, None, None)
        except CancelledError:
            pass

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=keep_helping) == 1


def test_join_inserts_named_system_row_and_visitor_message_does_not_create_bot_rows(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _delay_bot_turn(monkeypatch)
    ctx = _boot(client)

    with client.websocket_connect("/ws/agent", headers={"Origin": STAFF_ORIGIN}) as agent:
        auth_agent(agent, ctx["access_token"])
        with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
            auth_visitor(visitor, ctx["bootstrap_token"])
            collect_until(
                visitor, lambda frames: any(frame.get("type") == "state" for frame in frames)
            )
            visitor.send_json(
                {
                    "v": 1,
                    "type": "prechat",
                    "submission_id": PRECHAT_SUBMISSION_ID,
                    "name": "Ada Lopez",
                    "email": "ada@example.com",
                    "phone": "",
                    "inquiry_type": "results",
                    "message": DOT_QUESTION,
                }
            )
            started = collect_until(
                visitor,
                lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
            )
            conversation_id = conversation_id_from_state(started)
            agent.send_json(
                {
                    "v": 1,
                    "type": "subscribe",
                    "conversation_id": conversation_id,
                    "last_event_id": 0,
                }
            )
            agent.send_json({"v": 1, "type": "join", "conversation_id": conversation_id})
            visitor_join = collect_until(
                visitor,
                lambda frames: any(
                    frame.get("type") == "message" and frame.get("body") == JOIN_LINE_ALEX
                    for frame in frames
                ),
            )
            agent_join = collect_until(
                agent,
                lambda frames: any(
                    frame.get("type") == "message" and frame.get("body") == JOIN_LINE_ALEX
                    for frame in frames
                ),
            )
            visitor.send_json(
                {
                    "v": 1,
                    "type": "message",
                    "client_message_id": VISITOR_MESSAGE_ID,
                    "body": STILL_THERE,
                }
            )
            collect_until(
                visitor, lambda frames: any(frame.get("type") == "ack" for frame in frames)
            )

    system_on_visitor = [
        frame
        for frame in visitor_join
        if frame.get("type") == "message" and frame.get("body") == JOIN_LINE_ALEX
    ]
    system_on_agent = [
        frame
        for frame in agent_join
        if frame.get("type") == "message" and frame.get("body") == JOIN_LINE_ALEX
    ]
    assert len(system_on_visitor) == 1
    assert len(system_on_agent) == 1
    assert system_on_visitor[0]["role"] == "system"
    assert conversation_state(uuid.UUID(conversation_id)) == "human"
    assert assigned_agent_id(uuid.UUID(conversation_id)) is not None
    assert message_count(uuid.UUID(conversation_id), role="system", body=JOIN_LINE_ALEX) == 1
    assert message_count(uuid.UUID(conversation_id), body=STILL_THERE) == 1
    assert bot_row_count() == 0


def test_two_agents_race_join_one_winner_loser_cannot_send(client: TestClient) -> None:
    ctx = _boot(client)
    insert_staff(JORDAN_EMAIL, JORDAN_NAME, JORDAN_PASSWORD)
    jordan_token = login_staff(client, JORDAN_EMAIL, JORDAN_PASSWORD)

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, ctx["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": PRECHAT_SUBMISSION_ID,
                "name": "Ada Lopez",
                "email": "ada@example.com",
                "phone": "",
                "inquiry_type": "other",
                "message": "",
            }
        )
        started = collect_until(
            visitor,
            lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
        )
        conversation_id = conversation_id_from_state(started)

        with client.websocket_connect("/ws/agent", headers={"Origin": STAFF_ORIGIN}) as alex:
            auth_agent(alex, ctx["access_token"])
            with client.websocket_connect("/ws/agent", headers={"Origin": STAFF_ORIGIN}) as jordan:
                auth_agent(jordan, jordan_token)

                def _join(websocket: object) -> None:
                    websocket.send_json(  # type: ignore[attr-defined]
                        {"v": 1, "type": "join", "conversation_id": conversation_id}
                    )

                with ThreadPoolExecutor(max_workers=2) as pool:
                    pool.submit(_join, alex).result()
                    pool.submit(_join, jordan).result()

                alex_frames = collect_until(
                    alex,
                    lambda frames: any(
                        frame.get("type") == "state"
                        or (frame.get("type") == "error" and frame.get("code") == "already_joined")
                        for frame in frames
                    ),
                )
                jordan_frames = collect_until(
                    jordan,
                    lambda frames: any(
                        frame.get("type") == "state"
                        or (frame.get("type") == "error" and frame.get("code") == "already_joined")
                        for frame in frames
                    ),
                )
                errors = frames_of_type(alex_frames, "error") + frames_of_type(
                    jordan_frames, "error"
                )
                already = [frame for frame in errors if frame.get("code") == "already_joined"]
                assert len(already) == 1
                assert already[0]["display_name"] in {ALEX_NAME, JORDAN_NAME}
                loser = alex if already[0]["display_name"] == JORDAN_NAME else jordan
                loser.send_json(
                    {
                        "v": 1,
                        "type": "message",
                        "conversation_id": conversation_id,
                        "client_message_id": AGENT_MESSAGE_ID,
                        "body": AGENT_HELP,
                    }
                )
                denied = collect_until(
                    loser,
                    lambda frames: any(frame.get("type") == "error" for frame in frames),
                )

    assert frames_of_type(denied, "error")[-1]["code"] in {
        "already_joined",
        "not_assigned",
    }
    assert conversation_state(uuid.UUID(conversation_id)) == "human"
    winner_line = f"You're now chatting with {already[0]['display_name']}."
    assert message_count(uuid.UUID(conversation_id), role="system", body=winner_line) == 1
    assert assigned_agent_id(uuid.UUID(conversation_id)) is not None
    assert message_count(uuid.UUID(conversation_id), role="agent") == 0
    assert bot_row_count() == 0


ASSISTANT_LINE = "You're now chatting with the assistant."


def test_agent_can_transfer_joined_chat_back_to_the_assistant(client: TestClient) -> None:
    ctx = _boot(client)

    with client.websocket_connect("/ws/agent", headers={"Origin": STAFF_ORIGIN}) as agent:
        auth_agent(agent, ctx["access_token"])
        with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
            auth_visitor(visitor, ctx["bootstrap_token"])
            collect_until(
                visitor, lambda frames: any(frame.get("type") == "state" for frame in frames)
            )
            visitor.send_json(
                {
                    "v": 1,
                    "type": "prechat",
                    "submission_id": PRECHAT_SUBMISSION_ID,
                    "name": "Ada Lopez",
                    "email": "ada@example.com",
                    "phone": "",
                    "inquiry_type": "results",
                    "message": DOT_QUESTION,
                }
            )
            started = collect_until(
                visitor,
                lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
            )
            conversation_id = conversation_id_from_state(started)
            agent.send_json(
                {
                    "v": 1,
                    "type": "subscribe",
                    "conversation_id": conversation_id,
                    "last_event_id": 0,
                }
            )
            agent.send_json({"v": 1, "type": "join", "conversation_id": conversation_id})
            collect_until(
                visitor,
                lambda frames: any(
                    frame.get("type") == "message" and frame.get("body") == JOIN_LINE_ALEX
                    for frame in frames
                ),
            )
            agent.send_json({"v": 1, "type": "transfer_to_bot", "conversation_id": conversation_id})
            agent_transfer = collect_until(
                agent,
                lambda frames: any(
                    (frame.get("type") == "state" and frame.get("state") == "bot")
                    or frame.get("type") == "error"
                    for frame in frames
                ),
            )
            assert frames_of_type(agent_transfer, "error") == []
            assert frames_of_type(agent_transfer, "state")[-1]["state"] == "bot"
            visitor_transfer = collect_until(
                visitor,
                lambda frames: any(
                    frame.get("type") == "message" and frame.get("body") == ASSISTANT_LINE
                    for frame in frames
                ),
            )

    assert frames_of_type(visitor_transfer, "message")[-1]["body"] == ASSISTANT_LINE
    assert conversation_state(uuid.UUID(conversation_id)) == "bot"
    assert assigned_agent_id(uuid.UUID(conversation_id)) is None
    assert message_count(uuid.UUID(conversation_id), role="system", body=ASSISTANT_LINE) == 1
    assert message_count(uuid.UUID(conversation_id), role="system", body=JOIN_LINE_ALEX) == 1


def test_concurrent_identifies_with_one_resume_token_create_no_conversation(
    client: TestClient,
) -> None:
    seed_demo_world()
    first = post_bootstrap(client)
    resume = first.json()["resume_token"]
    first_claims = decode_widget_token(first.json()["bootstrap_token"])

    def _again() -> None:
        response = post_bootstrap(
            client,
            {"site_key": DEMO_SITE_KEY, "public_key": DEMO_PUBLIC_KEY, "resume_token": resume},
        )
        assert response.status_code == 200
        claims = decode_widget_token(response.json()["bootstrap_token"])
        assert "conversation_id" not in claims

    with ThreadPoolExecutor(max_workers=2) as pool:
        left = pool.submit(_again)
        right = pool.submit(_again)
        left.result()
        right.result()

    visitor_id = uuid.UUID(first_claims["visitor_id"])
    assert visitor_count() == 1
    assert conversation_count(visitor_id=visitor_id, open_only=True) == 0
    assert len(open_conversations_for_visitor(visitor_id)) == 0


def test_oversize_body_and_foreign_page_url_persist_nothing(client: TestClient) -> None:
    ctx = _boot(client)

    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, ctx["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json(
            {
                "v": 1,
                "type": "hello",
                "page_url": "https://evil.test/demo?q=1",
                "page_title": "Testing LiveChat inhouse",
                "referrer": "",
            }
        )
        hello_error = collect_until(
            visitor, lambda frames: any(frame.get("type") == "error" for frame in frames)
        )
        assert frames_of_type(hello_error, "error")[-1]["code"] == "invalid"
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": PRECHAT_SUBMISSION_ID,
                "name": "Ada Lopez",
                "email": "ada@example.com",
                "phone": "",
                "inquiry_type": "results",
                "message": DOT_QUESTION,
            }
        )
        started = collect_until(
            visitor,
            lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
        )
        conversation_id = uuid.UUID(conversation_id_from_state(started))
        visitor.send_json(
            {
                "v": 1,
                "type": "message",
                "client_message_id": VISITOR_MESSAGE_ID,
                "body": "x" * 4001,
            }
        )
        oversize = collect_until(
            visitor, lambda frames: any(frame.get("type") == "error" for frame in frames)
        )
        assert frames_of_type(oversize, "error")[-1]["code"] == "oversize"
        visitor.send_text("{" + "a" * 16384 + "}")
        frame_error = collect_until(
            visitor, lambda frames: any(frame.get("type") == "error" for frame in frames)
        )
        assert frames_of_type(frame_error, "error")[-1]["code"] == "oversize"

    assert page_fields(conversation_id) == (None, None, None)
    assert message_count(conversation_id, body="x" * 4001) == 0
    assert message_count(conversation_id, role="visitor") == 1
    # Prechat may produce a Plan 14 bot boundary/gap; oversize body must not.
    assert message_count(conversation_id, body="x" * 4001) == 0


def test_bot_turn_crash_turns_typing_off_and_keeps_the_socket(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.conversation_service import ConversationService

    async def boom(self, conversation_id, generation_id):
        raise RuntimeError("provider down")

    monkeypatch.setattr(ConversationService, "run_bot_turn", boom)
    ctx = _boot(client)
    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, ctx["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": PRECHAT_SUBMISSION_ID,
                "name": "Ada Lopez",
                "email": "ada@example.com",
                "phone": "",
                "inquiry_type": "results",
                "message": DOT_QUESTION,
            }
        )
        frames = collect_until(
            visitor,
            lambda items: any(
                frame.get("type") == "typing" and frame.get("active") is False for frame in items
            ),
        )
        typing = frames_of_type(frames, "typing")
        assert typing[0]["active"] is True
        assert typing[-1]["active"] is False
        visitor.send_json({"v": 1, "type": "ping"})
        pong = collect_until(
            visitor, lambda items: any(frame.get("type") == "pong" for frame in items)
        )
        assert frames_of_type(pong, "pong")[-1]["type"] == "pong"


def test_visitor_socket_stays_open_during_long_bot_turn(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.chat.ws_visitor as ws_visitor
    from app.services.conversation_service import ConversationService

    monkeypatch.setattr(ws_visitor, "IDLE_CHECK_SECONDS", 0.15)
    monkeypatch.setattr(ws_visitor, "IDLE_PING_AFTER_SECONDS", 0.2)
    monkeypatch.setattr(ws_visitor, "IDLE_CLOSE_SECONDS", 0.6)
    original = ConversationService.run_bot_turn

    async def slow(self, conversation_id, generation_id, **kwargs):
        await asyncio.sleep(1.1)
        return await original(self, conversation_id, generation_id, **kwargs)

    monkeypatch.setattr(ConversationService, "run_bot_turn", slow)
    ctx = _boot(client)
    with client.websocket_connect("/ws/visitor", headers={"Origin": WIDGET_ORIGIN}) as visitor:
        auth_visitor(visitor, ctx["bootstrap_token"])
        collect_until(visitor, lambda frames: any(frame.get("type") == "state" for frame in frames))
        visitor.send_json(
            {
                "v": 1,
                "type": "prechat",
                "submission_id": PRECHAT_SUBMISSION_ID,
                "name": "Ada Lopez",
                "email": "ada@example.com",
                "phone": "",
                "inquiry_type": "results",
                "message": DOT_QUESTION,
            }
        )
        started = collect_until(
            visitor,
            lambda frames: any(frame.get("type") == "prechat_accepted" for frame in frames),
        )
        conversation_id = uuid.UUID(conversation_id_from_state(started))
        frames: list[dict] = []
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            visitor_socket = visitor
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    frame = pool.submit(visitor_socket.receive_json).result(timeout=remaining)
            except Exception as exc:
                raise AssertionError(
                    f"socket failed during bot turn: {exc!r} frames={frames!r}"
                ) from exc
            frames.append(frame)
            if frame.get("type") == "ping":
                visitor.send_json({"v": 1, "type": "pong"})
            if frame.get("type") == "typing" and frame.get("active") is False:
                break
        else:
            raise AssertionError(f"bot turn never finished; frames={frames!r}")
        assert any(frame.get("type") == "ping" for frame in frames)
        visitor.send_json({"v": 1, "type": "ping"})
        pong = collect_until(
            visitor, lambda items: any(frame.get("type") == "pong" for frame in items)
        )
        assert frames_of_type(pong, "pong")[-1]["type"] == "pong"
    assert bot_row_count() + message_count(conversation_id, role="system") >= 1


async def test_parallel_identify_reuses_the_visitor_without_opening_a_chat(migrated_db) -> None:
    from sqlalchemy import func, select

    from app.db import session_maker
    from app.models.conversation import Conversation
    from app.services.conversation_service import ConversationService
    from tests.bot_fixtures import insert_site as insert_site_async

    async with session_maker()() as session:
        site = await insert_site_async(session, "samplesite", "SampleSite")
        await session.commit()
        first = await ConversationService(session).bootstrap(
            site.key,
            site.public_key,
            HOST_ORIGIN,
            None,
            "203.0.113.9",
            "Mozilla/5.0",
        )
        assert first.conversation_id is None
        site_key = site.key
        public_key = site.public_key
        resume = first.resume_token
        visitor_id = first.visitor_id

    async def once() -> uuid.UUID | None:
        async with session_maker()() as session:
            result = await ConversationService(session).bootstrap(
                site_key,
                public_key,
                HOST_ORIGIN,
                resume,
                "203.0.113.9",
                "Mozilla/5.0",
            )
            assert result.mode == "conversation"
            assert result.conversation_id is None
            return result.visitor_id

    left, right = await asyncio.gather(once(), once())
    assert left == right == visitor_id
    async with session_maker()() as session:
        open_count = int(
            await session.scalar(
                select(func.count())
                .select_from(Conversation)
                .where(Conversation.visitor_id == visitor_id, Conversation.state != "closed")
            )
            or 0
        )
    assert open_count == 0
