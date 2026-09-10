from unittest.mock import patch

import pytest

from app.services.kb_embedder import (
    FakeEmbedder,
    OpenAIEmbedder,
    OversizeChunkError,
    unit_vector,
)


async def test_fake_embedder_sees_timing_fact_past_two_thousand_chars() -> None:
    text = ("x" * 2100) + " 24-48 hours turnaround"
    vectors = await FakeEmbedder().embed_documents([text])
    assert vectors == [unit_vector(0)]


async def test_openai_embed_documents_raises_when_token_count_exceeds_cap(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_EMBED_MAX_TOKENS", "8000")

    class FakeEncoding:
        def encode(self, text: str) -> list[int]:
            return [0] * 9000

    class FakeEmbeddings:
        async def create(self, **kwargs):
            raise AssertionError("embed API must not be called for an oversize chunk")

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.embeddings = FakeEmbeddings()

        async def close(self) -> None:
            return None

    with (
        patch("app.services.kb_embedder.encoding_for_model", lambda _name: FakeEncoding()),
        patch("openai.AsyncOpenAI", FakeClient),
        pytest.raises(OversizeChunkError),
    ):
        await OpenAIEmbedder("sk-test").embed_documents(["hello"])
