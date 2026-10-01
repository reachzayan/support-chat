"""End-to-end coverage for the temporary, local-only chatbot workbench."""

import asyncio
from types import SimpleNamespace
from uuid import UUID

import pytest
from anthropic.types import Message as AnthropicMessage
from fastapi.testclient import TestClient

import app.main as main_module
from app.db import reset_engine, session_maker
from app.llm.bot_responder import BotResponder
from app.models.user import User
from app.security.deps import get_current_admin
from app.settings import reset_settings_cache
from tests.bot_fixtures import insert_chunk, insert_site

SERVICE_FACT = (
    "Sample Data Services gathers information from trusted sources and provides identity "
    "verification data to regulated businesses."
)
SERVICE_REPLY = (
    "Sample Data Services gathers trusted information to help regulated businesses verify identities."
)
SIMPLE_REPLY = (
    "In simple terms, Sample Data Services collects reliable information so regulated businesses "
    "can confirm identities."
)
VBANK_FACT = "VBANK verifies bank account ownership."
VBANK_REPLY = "VBANK helps verify who owns a bank account."


class _GroundedMessages:
    async def create(self, **kwargs):
        latest = str(kwargs["messages"][-1]["content"])
        documents = kwargs["messages"][0]["content"]
        if "VBANK" in latest:
            needle, answer = VBANK_FACT, VBANK_REPLY
        elif "simpl" in latest.casefold():
            needle, answer = SERVICE_FACT, SIMPLE_REPLY
        else:
            needle, answer = SERVICE_FACT, SERVICE_REPLY

        for index, document in enumerate(documents):
            source = document["source"]["data"]
            if needle not in source:
                continue
            return AnthropicMessage.model_validate(
                {
                    "id": "msg_internal_dev_e2e",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-haiku-4-5",
                    "content": [
                        {
                            "type": "text",
                            "text": answer,
                            "citations": [
                                {
                                    "type": "char_location",
                                    "document_index": index,
                                    "document_title": document["title"],
                                    "start_char_index": 0,
                                    "end_char_index": len(source),
                                    "cited_text": source,
                                }
                            ],
                        }
                    ],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 100, "output_tokens": 20},
                }
            )

        return SimpleNamespace(
            content=[],
            stop_reason="end_turn",
            _request_id="missing-document",
            usage=None,
        )


class _GroundedClient:
    def __init__(self, **_kwargs):
        self.messages = _GroundedMessages()

    async def close(self):
        return None


async def _seed_workbench() -> tuple[UUID, UUID]:
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "Sample Data Services")
        service = await insert_chunk(session, site, "Our services", SERVICE_FACT, "services")
        # The regression must not pass because the generic follow-up happens to
        # resemble the source in embedding space.
        service.embedding = None
        vbank = await insert_chunk(session, site, "What is VBANK?", VBANK_FACT, "vbank")
        vbank.embedding = None
        await session.commit()
        return service.id, vbank.id


@pytest.fixture
def workbench_client(migrated_db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("INTERNAL_EVAL_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    reset_settings_cache()
    monkeypatch.setattr("app.llm.bot_responder.AsyncAnthropic", _GroundedClient)
    BotResponder._shared_client = None
    BotResponder._shared_client_factory = None
    service_id, vbank_id = asyncio.run(_seed_workbench())
    reset_engine()

    application = main_module.create_app()
    application.dependency_overrides[get_current_admin] = lambda: User(is_admin=True)
    with TestClient(application) as client:
        yield client, service_id, vbank_id
    application.dependency_overrides.clear()


def _reply(payload: dict) -> dict:
    reply = payload["reply"]
    assert reply is not None
    return reply


def test_trace_endpoint_preserves_evidence_for_implicit_misspelled_follow_up(
    workbench_client,
) -> None:
    client, service_id, _vbank_id = workbench_client

    first = client.post(
        "/api/internal/dev/chat",
        json={"site_key": "samplesite", "message": "what services do you provide?"},
    )
    assert first.status_code == 200
    assert "/api/internal/dev/chat" not in client.get("/openapi.json").json()["paths"]
    assert "/api/internal/dev/trace" not in client.get("/openapi.json").json()["paths"]
    assert "/api/internal/dev/canned-search" not in client.get("/openapi.json").json()["paths"]
    first_data = first.json()
    assert _reply(first_data)["body"] == SERVICE_REPLY

    second = client.post(
        "/api/internal/dev/trace",
        json={
            "site_key": "samplesite",
            "conversation_id": first_data["conversation_id"],
            "message": "can u explane in simplr words?",
        },
    )
    assert second.status_code == 200
    data = second.json()
    assert _reply(data)["body"] == SIMPLE_REPLY
    assert _reply(data)["source_chunk_ids"] == [str(service_id)]
    assert data["trace"]["retrieval"]["query"] == "can u explane in simplr words?"
    assert data["trace"]["retrieval"]["carried_evidence_ids"] == [str(service_id)]
    assert data["trace"]["provider"]["document_count"] >= 1
    assert data["trace"]["decision"]["persisted"] is True


def test_current_topic_evidence_wins_over_carried_conversation_evidence(
    workbench_client,
) -> None:
    client, _service_id, vbank_id = workbench_client
    first = client.post(
        "/api/internal/dev/chat",
        json={"site_key": "samplesite", "message": "what services do you provide?"},
    )
    assert first.status_code == 200

    switched = client.post(
        "/api/internal/dev/trace",
        json={
            "site_key": "samplesite",
            "conversation_id": first.json()["conversation_id"],
            "message": "What is VBANK?",
        },
    )
    assert switched.status_code == 200
    data = switched.json()
    assert _reply(data)["body"] == VBANK_REPLY
    assert _reply(data)["source_chunk_ids"] == [str(vbank_id)]
    assert str(vbank_id) in data["trace"]["retrieval"]["current_evidence_ids"]
