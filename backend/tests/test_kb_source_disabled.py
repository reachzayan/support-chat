from uuid import uuid4

from app.db import session_maker
from app.models.kb_source import KbSource
from app.services.full_context import clear_units_cache, load_approved_units
from app.services.kb_embedder import FakeEmbedder, configured_embedder_id
from app.services.kb_ingest import ingest_source
from app.services.kb_source_admin import KbSourceService
from app.services.route_decision import live_snapshots_for_site
from tests.bot_fixtures import insert_site

FAQ_URL = "https://sample-site.example.com/faq"
FAQ_HTML = (
    "<html><body><main><h1>Turnaround</h1>"
    "<p>Most negative results are reported within 24-48 hours.</p></main></body></html>"
)


def _fetch(_url: str, _hosts: set[str], hops: int = 0) -> str:
    return FAQ_HTML


async def _ready_source(session) -> KbSource:
    site = await insert_site(session, f"easy-{uuid4().hex[:8]}", "SampleSite")
    site.allowed_origins = ["https://sample-site.example.com"]
    source = KbSource(
        site_id=site.id,
        start_url=FAQ_URL,
        mode="list",
        seed_urls=[FAQ_URL],
        status="queued",
        embedder_id=configured_embedder_id(),
        enabled=True,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def test_disabled_source_excluded_from_live_snapshots_and_cache(migrated_db) -> None:
    clear_units_cache()
    async with session_maker()() as session:
        source = await _ready_source(session)
        source_id = source.id
        site_id = source.site_id
        await ingest_source(session, source_id, embedder=FakeEmbedder(), fetch=_fetch)

    async with session_maker()() as session:
        live_before = await live_snapshots_for_site(session, site_id)
        assert len(live_before) == 1
        snapshot_id = live_before[0].id
        warmed = await load_approved_units(session, [snapshot_id])
        assert len(warmed) == 1

        service = KbSourceService(session)
        await service.patch_source(source_id, enabled=False)

    async with session_maker()() as session:
        live_after = await live_snapshots_for_site(session, site_id)
        assert live_after == []
        cached = await load_approved_units(session, [snapshot_id])
        assert cached == []
