import uuid

from app.db import session_maker
from app.services.kb_embedder import rrf_merge, unit_vector
from app.services.kb_search import KbSearch
from tests.bot_fixtures import (
    EASY_BODY,
    FAST_QUERY,
    FCRA_BODY,
    seed_brand_articles,
)

A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
C = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def test_rrf_merges_fts_and_dense_in_b_a_c_order() -> None:
    ranked = rrf_merge([A, B], [B, C], k=60)
    scores = {chunk_id: score for chunk_id, score in ranked}
    assert [chunk_id for chunk_id, _score in ranked] == [B, A, C]
    assert round(scores[A], 5) == round(1 / 61, 5)
    assert round(scores[B], 5) == round(1 / 62 + 1 / 61, 5)
    assert round(scores[C], 5) == round(1 / 62, 5)


async def test_hybrid_timing_query_stays_on_samplesite(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, timing, _fcra = await seed_brand_articles(session)
        hits = await KbSearch(session).search(easy.id, FAST_QUERY, query_vector=unit_vector(0))
        assert [hit.body for hit in hits] == [EASY_BODY]
        assert [hit.id for hit in hits] == [timing.chunk_id]


async def test_fcra_vector_on_samplesite_does_not_leak_background_checks(
    migrated_db,
) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        hits = await KbSearch(session).search(easy.id, "what is FCRA", query_vector=unit_vector(1))
        assert hits == []


async def test_embed_timeout_falls_open_to_fts(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        hits = await KbSearch(session).search(easy.id, FAST_QUERY, query_vector=None)
        assert "24-48 hours" in hits[0].body
        assert all(hit.site_id == easy.id for hit in hits)


async def test_overview_question_uses_that_sites_indexed_copy(migrated_db) -> None:
    async with session_maker()() as session:
        easy, bg, _timing, _fcra = await seed_brand_articles(session)
        easy_hits = await KbSearch(session).search(
            easy.id, "can you tell me what you guys do", query_vector=None
        )
        bg_hits = await KbSearch(session).search(
            bg.id, "can you tell me what you guys do", query_vector=None
        )
        assert [hit.body for hit in easy_hits] == [EASY_BODY]
        assert [hit.body for hit in bg_hits] == [FCRA_BODY]
        assert all(hit.site_id == easy.id for hit in easy_hits)
        assert all(hit.site_id == bg.id for hit in bg_hits)


async def test_empty_index_returns_no_hits(migrated_db) -> None:
    async with session_maker()() as session:
        _easy, bg, _timing, _fcra = await seed_brand_articles(session)
        hits = await KbSearch(session).search(bg.id, FAST_QUERY, query_vector=unit_vector(0))
        assert hits == []
        assert FCRA_BODY not in FAST_QUERY
