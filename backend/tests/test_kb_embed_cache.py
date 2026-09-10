from hashlib import sha256
from json import dumps, loads
from unittest.mock import patch

from app.services.kb_embedder import OpenAIEmbedder, document_vector_cache_key


class _MemoryRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value


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
