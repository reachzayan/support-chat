from hashlib import sha256
from json import dumps, loads
from typing import Protocol
from uuid import UUID

from app.redis import get_redis
from app.services.kb_tokens import normalize_query
from app.settings import get_settings


class OversizeChunkError(Exception):
    pass


class Embedder(Protocol):
    embedder_id: str
    dim: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float] | None: ...


def encoding_for_model(name: str):
    import tiktoken

    try:
        return tiktoken.encoding_for_model(name)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def count_embed_tokens(text: str) -> int:
    settings = get_settings()
    return len(encoding_for_model(settings.openai_embed_model).encode(text))


def split_text_to_token_limit(text: str, max_tokens: int) -> list[str]:
    if not text:
        return []
    if max_tokens < 1:
        raise OversizeChunkError("oversize")
    encoding = encoding_for_model(get_settings().openai_embed_model)
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        piece = encoding.decode(tokens[start:end])
        if not piece:
            raise OversizeChunkError("oversize")
        pieces.append(piece)
        start = end
    return pieces


def configured_embedder_id() -> str:
    settings = get_settings()
    return f"openai:{settings.openai_embed_model}:{settings.openai_embed_dim}"


def unit_vector(axis: int, dim: int | None = None) -> list[float]:
    size = get_settings().openai_embed_dim if dim is None else dim
    vector = [0.0] * size
    if 0 <= axis < size:
        vector[axis] = 1.0
    return vector


def axis_for_text(text: str) -> int:
    lowered = text.casefold()
    if any(token in lowered for token in ("24-48", "how fast", "turnaround", "how long")):
        return 0
    if "fcra" in lowered or "fair credit" in lowered:
        return 1
    if any(token in lowered for token in ("pricing", "how much", "cost", "price")):
        return 2
    if "dot" in lowered:
        return 3
    if "portal" in lowered:
        return 4
    return 10


def query_vector_cache_key(normalized_query: str) -> str:
    digest = sha256(normalized_query.encode("utf-8")).hexdigest()
    return f"kb:qvec:{digest}"


def document_vector_cache_key(text: str, embedder_id: str) -> str:
    digest = sha256(text.encode("utf-8")).hexdigest()
    return f"kb:embed:v1:{digest}:{embedder_id}"


EMBED_DOC_TTL = 30 * 24 * 60 * 60


async def _cached_query_vector(normalized_query: str) -> list[float] | None:
    if not normalized_query:
        return None
    try:
        raw = await get_redis().get(query_vector_cache_key(normalized_query))
    except Exception:
        return None
    if not raw:
        return None
    try:
        parsed = loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, list) or not parsed:
        return None
    return [float(item) for item in parsed]


async def _store_query_vector(normalized_query: str, vector: list[float]) -> None:
    if not normalized_query or not vector:
        return
    settings = get_settings()
    try:
        await get_redis().set(
            query_vector_cache_key(normalized_query),
            dumps(vector),
            ex=settings.query_vector_cache_ttl,
        )
    except Exception:
        return


async def _cached_document_vector(text: str, embedder_id: str) -> list[float] | None:
    if not text:
        return None
    try:
        raw = await get_redis().get(document_vector_cache_key(text, embedder_id))
    except Exception:
        return None
    if not raw:
        return None
    try:
        parsed = loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, list) or not parsed:
        return None
    return [float(item) for item in parsed]


async def _store_document_vector(text: str, embedder_id: str, vector: list[float]) -> None:
    if not text or not vector:
        return
    try:
        await get_redis().set(
            document_vector_cache_key(text, embedder_id),
            dumps(vector),
            ex=EMBED_DOC_TTL,
        )
    except Exception:
        return


class FakeEmbedder:
    embedder_id = "fake:axes"

    @property
    def dim(self) -> int:
        return get_settings().openai_embed_dim

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [unit_vector(axis_for_text(text)) for text in texts]

    async def embed_query(self, text: str) -> list[float] | None:
        return unit_vector(axis_for_text(text))


class OpenAIEmbedder:
    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key

    @property
    def model(self) -> str:
        return get_settings().openai_embed_model

    @property
    def dim(self) -> int:
        return get_settings().openai_embed_dim

    @property
    def embedder_id(self) -> str:
        return configured_embedder_id()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        from openai import APITimeoutError, AsyncOpenAI, RateLimitError

        settings = get_settings()
        limit = settings.openai_embed_max_tokens
        for item in texts:
            if count_embed_tokens(item) > limit:
                raise OversizeChunkError("oversize")
        embedder_id = self.embedder_id
        vectors: list[list[float] | None] = [None] * len(texts)
        missing: list[int] = []
        for index, item in enumerate(texts):
            cached = await _cached_document_vector(item, embedder_id)
            if cached is not None:
                vectors[index] = cached
            else:
                missing.append(index)
        if not missing:
            return [item for item in vectors if item is not None]
        client = AsyncOpenAI(api_key=self._api_key, timeout=settings.embed_ingest_timeout)
        try:
            batch_size = settings.embed_batch
            pending_texts = [texts[index] for index in missing]
            fetched: list[list[float]] = []
            for start in range(0, len(pending_texts), batch_size):
                batch = pending_texts[start : start + batch_size]
                response = await _embed_with_retry(
                    client,
                    model=settings.openai_embed_model,
                    batch=batch,
                    dimensions=settings.openai_embed_dim,
                    rate_error=RateLimitError,
                    timeout_error=APITimeoutError,
                )
                ordered = sorted(response.data, key=lambda row: row.index)
                fetched.extend(list(row.embedding) for row in ordered)
        finally:
            await client.close()
        for offset, index in enumerate(missing):
            vector = fetched[offset]
            vectors[index] = vector
            await _store_document_vector(texts[index], embedder_id, vector)
        return [item for item in vectors if item is not None]

    async def embed_query(self, text: str) -> list[float] | None:
        from openai import APITimeoutError, AsyncOpenAI

        if not self._api_key:
            return None
        settings = get_settings()
        normalized = normalize_query(text)
        cached = await _cached_query_vector(normalized)
        if cached is not None:
            return cached
        if count_embed_tokens(text) > settings.openai_embed_max_tokens:
            return None
        client = AsyncOpenAI(
            api_key=self._api_key, timeout=settings.embed_query_timeout, max_retries=0
        )
        try:
            response = await client.embeddings.create(
                model=settings.openai_embed_model,
                input=text,
                dimensions=settings.openai_embed_dim,
                encoding_format="float",
            )
        except (APITimeoutError, OSError, TimeoutError):
            return None
        finally:
            await client.close()
        vector = list(response.data[0].embedding)
        await _store_query_vector(normalized, vector)
        return vector


async def _embed_with_retry(
    client, *, model: str, batch: list[str], dimensions: int, rate_error, timeout_error
):
    import asyncio

    last_error: Exception | None = None
    for attempt in range(5):
        try:
            return await client.embeddings.create(
                model=model,
                input=batch,
                dimensions=dimensions,
                encoding_format="float",
            )
        except rate_error as exc:
            last_error = exc
            await asyncio.sleep(min(2**attempt, 30))
        except timeout_error as exc:
            raise exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("embed retry exhausted")


def default_embedder() -> Embedder:
    key = get_settings().openai_api_key
    if not key:
        return FakeEmbedder()
    return OpenAIEmbedder(key)


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


RRF_K = 60


def rrf_merge(
    fts_ids: list[UUID],
    dense_ids: list[UUID],
    overview_ids: list[UUID] | None = None,
    k: int = RRF_K,
) -> list[tuple[UUID, float]]:
    scores: dict[UUID, float] = {}
    for rank, chunk_id in enumerate(fts_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    for rank, chunk_id in enumerate(dense_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    for rank, chunk_id in enumerate(overview_ids or [], start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))
