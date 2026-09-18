from hashlib import sha256
from json import dumps, loads
from unittest.mock import patch

from app.services.bot_trace import capture_trace
from app.services.kb_embedder import (
    OpenAIEmbedder,
    document_vector_cache_key,
    query_vector_cache_key,
)


class _MemoryRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.expiry: dict[str, int | None] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        self.expiry[key] = ex


async def test_embed_documents_skips_api_on_redis_cache_hit(monkeypatch) -> None:
    redis = _MemoryRedis()
    calls = {"n": 0}

    class FakeEmbeddings:
        async def create(self, **kwargs):
            calls["n"] += 1
            row = type("Row", (), {"index": 0, "embedding": [0.25, 0.0]})()
            return type("Resp", (), {"data": [row]})()

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.embeddings = FakeEmbeddings()

        async def close(self) -> None:
            return None

    monkeypatch.setenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENAI_EMBED_DIM", "2")
    with (
        patch("openai.AsyncOpenAI", FakeClient),
        patch("app.services.kb_embedder.get_redis", lambda: redis),
    ):
        embedder = OpenAIEmbedder("sk-test")
        first = await embedder.embed_documents(["how fast are results"])
        second = await embedder.embed_documents(["how fast are results"])

    assert first == [[0.25, 0.0]]
    assert second == [[0.25, 0.0]]
    assert calls["n"] == 1
    key = document_vector_cache_key("how fast are results", embedder.embedder_id)
    digest = sha256(b"how fast are results").hexdigest()
    assert key == f"kb:embed:v1:{digest}:{embedder.embedder_id}"
    assert loads(redis.store[key]) == [0.25, 0.0]
    assert dumps([0.25, 0.0]) == redis.store[key]


async def test_query_embeddings_reuse_the_client_and_a_versioned_day_cache(monkeypatch) -> None:
    redis = _MemoryRedis()
    client_count = 0
    api_calls = 0

    class FakeEmbeddings:
        async def create(self, **kwargs):
            nonlocal api_calls
            api_calls += 1
            row = type("Row", (), {"index": 0, "embedding": [0.5, 0.0]})()
            return type("Resp", (), {"data": [row]})()

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            nonlocal client_count
            client_count += 1
            self.embeddings = FakeEmbeddings()

        async def close(self) -> None:
            return None

    monkeypatch.setenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENAI_EMBED_DIM", "2")
    monkeypatch.setenv("QUERY_VECTOR_CACHE_TTL", "86400")
    with (
        patch("openai.AsyncOpenAI", FakeClient),
        patch("app.services.kb_embedder.get_redis", lambda: redis),
    ):
        await OpenAIEmbedder.close_shared_clients()
        embedder = OpenAIEmbedder("sk-test")
        with capture_trace() as trace:
            first = await embedder.embed_query("What is SampleMail?")
            second = await embedder.embed_query("  what   is samplemail? ")
        third = await OpenAIEmbedder("sk-test").embed_query("What is VBANK?")
        await OpenAIEmbedder.close_shared_clients()

    assert first == second == third == [0.5, 0.0]
    assert api_calls == 2
    assert client_count == 1
    key = query_vector_cache_key("what is samplemail?", embedder.embedder_id)
    assert loads(redis.store[key]) == [0.5, 0.0]
    assert redis.expiry[key] == 86400
    assert trace["retrieval"]["query_vector_cache_hit"] is True
