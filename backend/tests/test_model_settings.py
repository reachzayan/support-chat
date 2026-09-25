from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from app.llm.bot_responder import BotResponder
from app.services.grounded_response import EvidenceUnit, TurnContext
from app.services.kb_embedder import OpenAIEmbedder, configured_embedder_id
from app.settings import Settings

_SECRETS = {
    "database_url": "postgresql://chat:chat@127.0.0.1:55432/support_chat_test",
    "jwt_secret": "a8f3c1e9b2d64750c4a1f8e3b6d9027c5e1a4b8f3c6d9e2a7b0c5d8e1f4a7b3c",
    "widget_token_secret": "d1e4a7b0c3f6d9e2a5b8c1d4e7f0a3b6c9d2e5f8a1b4c7d0e3f6a9b2c5d8e1f4",
    "rate_key_secret": "9c2f5a8d1e4b7c0f3a6d9e2b5c8f1a4d7e0b3c6f9a2d5e8b1c4f7a0d3e6b9c2f",
}

TIMING_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
EASY_BODY = "Most negative results are reported within 24-48 hours."


def test_settings_read_embed_model_and_generation_knobs_from_explicit_values() -> None:
    settings = Settings(
        **_SECRETS,
        openai_embed_model="text-embedding-3-large",
        openai_embed_dim=3072,
        anthropic_max_tokens=400,
    )
    assert settings.openai_embed_model == "text-embedding-3-large"
    assert settings.openai_embed_dim == 3072
    assert settings.anthropic_max_tokens == 400


def test_openai_embedder_id_follows_embed_model_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("OPENAI_EMBED_DIM", "3072")
    embedder = OpenAIEmbedder("sk-test")
    assert embedder.model == "text-embedding-3-large"
    assert embedder.dim == 3072
    assert embedder.embedder_id == "openai:text-embedding-3-large:3072"
    assert configured_embedder_id() == "openai:text-embedding-3-large:3072"


async def test_embed_documents_sends_the_configured_model(monkeypatch) -> None:
    captured: dict = {}

    class FakeEmbeddings:
        async def create(self, **kwargs):
            captured.update(kwargs)
            row = type("Row", (), {"index": 0, "embedding": [0.1, 0.0]})()
            return type("Resp", (), {"data": [row]})()

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.embeddings = FakeEmbeddings()

        async def close(self) -> None:
            return None

    monkeypatch.setenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("OPENAI_EMBED_DIM", "3072")
    with patch("openai.AsyncOpenAI", FakeClient):
        vectors = await OpenAIEmbedder("sk-test").embed_documents(["how fast are results"])
    assert captured["model"] == "text-embedding-3-large"
    assert captured["dimensions"] == 3072
    assert vectors == [[0.1, 0.0]]


async def test_bot_responder_uses_supported_sdk_parameters_and_fixed_token_cap(monkeypatch) -> None:
    captured: dict = {}

    class FakeMessages:
        async def create(self, *, model, max_tokens, system, messages):
            captured.update(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            block = type(
                "Block", (), {"type": "text", "text": f"{EASY_BODY}\nSOURCES: {TIMING_ID}"}
            )()
            return type("Response", (), {"content": [block]})()

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.messages = FakeMessages()

        async def close(self) -> None:
            return None

    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    monkeypatch.setenv("ANTHROPIC_MAX_TOKENS", "400")
    monkeypatch.setattr("app.llm.bot_responder.AsyncAnthropic", FakeClient, raising=False)
    hit = SimpleNamespace(
        id=TIMING_ID, title="Turnaround", heading="Turnaround", body=EASY_BODY, url=""
    )
    answer = await BotResponder().generate(SimpleNamespace(name="SampleSite"), "how fast", [hit])
    assert captured["model"] == "claude-haiku-4-5-20251001"
    assert captured["max_tokens"] == 400
    assert answer.accepted is True


async def test_grounded_responder_uses_the_installed_sdk_request_contract(monkeypatch) -> None:
    captured: dict = {}
    paraphrase = "Most negative results come back within 24-48 hours."

    class FakeMessages:
        async def create(self, *, model, max_tokens, system, messages):
            captured.update(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            citation = SimpleNamespace(
                document_index=0,
                start_char_index=0,
                end_char_index=len(EASY_BODY),
                cited_text=EASY_BODY,
            )
            block = SimpleNamespace(type="text", text=paraphrase, citations=[citation])
            return SimpleNamespace(content=[block])

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.messages = FakeMessages()

        async def close(self) -> None:
            return None

    monkeypatch.setattr("app.llm.bot_responder.AsyncAnthropic", FakeClient, raising=False)
    evidence = EvidenceUnit(
        id=TIMING_ID,
        canonical_question="How fast are results?",
        aliases=(),
        topic_label="Turnaround",
        answer_verbatim=EASY_BODY,
        source_title="Turnaround",
        source_url="https://example.test/turnaround",
    )

    draft = await BotResponder().generate_grounded_draft(
        TurnContext(visitor_text="how fast", evidence=[evidence], site_name="SampleSite"),
        [evidence],
    )

    assert draft is not None
    assert draft.body == paraphrase
    assert draft.citations[0].source_title == evidence.source_title
    assert draft.citations[0].source_url == evidence.source_url
    assert captured["max_tokens"] == 500
    assert set(captured) == {"model", "max_tokens", "system", "messages"}
