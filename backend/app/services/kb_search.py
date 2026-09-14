from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.kb_hybrid import ChunkHit, HybridKbSearch
from app.services.kb_tokens import normalize_query, search_tokens, tokenize

MAX_RESULTS = 5

__all__ = [
    "MAX_RESULTS",
    "ChunkHit",
    "KbSearch",
    "normalize_query",
    "search_tokens",
    "tokenize",
]


class KbSearch:
    def __init__(self, session: AsyncSession) -> None:
        self._inner = HybridKbSearch(session)

    async def search(
        self, site_id: UUID, visitor_text: str, query_vector: list[float] | None = None
    ) -> list[ChunkHit]:
        return await self._inner.search(site_id, visitor_text, query_vector)
