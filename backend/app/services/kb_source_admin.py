from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_page_llm_extract import KbPageLlmExtract
from app.models.kb_smoke_assertion import KbSmokeAssertion
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.site import Site
from app.models.user import User
from app.repositories.kb_snapshot_repo import KbSnapshotRepository
from app.repositories.kb_source_repo import KbSourceRepository
from app.services.full_context import clear_units_cache
from app.services.kb_embedder import configured_embedder_id
from app.services.kb_ingest import CanonicalError, canonical_fetch_url, enqueue_wakeup, host_allowed
from app.services.site_admin import AdminError

SAMPLESITE_SMOKE = ["24-48", "MRO", "rapid"]


class KbSourceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_sources(self, site_id: UUID) -> list[KbSource]:
        site = await self._session.get(Site, site_id)
        if site is None:
            raise AdminError("not_found")
        result = await self._session.execute(
            select(KbSource).where(KbSource.site_id == site_id).order_by(KbSource.created_at)
        )
        return list(result.scalars().all())

    async def create_source(
        self,
        site_id: UUID,
        admin: User,
        *,
        mode: str,
        start_url: str,
        seed_urls: list[str],
    ) -> KbSource:
        site = await self._session.get(Site, site_id)
        if site is None:
            raise AdminError("not_found")
        if mode not in {"list", "prefix"}:
            raise AdminError("invalid")
        try:
            start_url = canonical_fetch_url(start_url)
        except CanonicalError:
            raise AdminError("invalid") from None
        raw_seeds = seed_urls if mode == "list" else [start_url]
        urls = self._normalized_seed_urls(raw_seeds)
        self._assert_seed_hosts(urls, site, start_url)
        existing = await KbSourceRepository(self._session).get_by_site_start_url(site_id, start_url)
        if existing is not None:
            existing.mode = mode
            existing.seed_urls = urls
            existing.status = "queued"
            existing.stage = "idle"
            existing.error_code = None
            existing.enabled = True
            await self._ensure_samplesite_smoke(existing)
            await self._session.commit()
            await enqueue_wakeup(existing.id)
            return existing
        source = KbSource(
            site_id=site_id,
            start_url=start_url,
            mode=mode,
            seed_urls=urls,
            status="queued",
            embedder_id=configured_embedder_id(),
            created_by=admin.id,
            enabled=True,
        )
        self._session.add(source)
        await self._session.flush()
        await self._ensure_samplesite_smoke(source)
        await self._session.commit()
        await enqueue_wakeup(source.id)
        return source

    @staticmethod
    def _normalized_seed_urls(raw_seeds: list[str]) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for raw in raw_seeds:
            try:
                fetch_url = canonical_fetch_url(raw)
            except CanonicalError:
                raise AdminError("invalid") from None
            if fetch_url in seen:
                continue
            seen.add(fetch_url)
            urls.append(raw.strip())
        if not urls:
            raise AdminError("invalid")
        if len(urls) > 50:
            raise AdminError("too_large")
        return urls

    @staticmethod
    def _assert_seed_hosts(urls: list[str], site: Site, start_url: str) -> None:
        for raw in urls:
            fetch_url = canonical_fetch_url(raw)
            if not host_allowed(fetch_url, site, start_url):
                raise AdminError("invalid_origin")

    async def _ensure_samplesite_smoke(self, source: KbSource) -> None:
        if "sample-site.example.com" not in source.start_url.casefold():
            return
        existing = await self._session.scalar(
            select(KbSmokeAssertion.id).where(KbSmokeAssertion.source_id == source.id)
        )
        if existing is not None:
            return
        self._session.add(
            KbSmokeAssertion(
                source_id=source.id,
                must_include=list(SAMPLESITE_SMOKE),
                must_exclude=[],
            )
        )

    async def patch_source(self, source_id: UUID, *, enabled: bool | None) -> KbSource:
        source = await self._session.get(KbSource, source_id)
        if source is None:
            raise AdminError("not_found")
        if enabled is not None:
            source.enabled = enabled
        await self._session.commit()
        if enabled is not None:
            clear_units_cache()
        return source

    async def sync_source(self, source_id: UUID) -> KbSource:
        source = await self._session.get(KbSource, source_id)
        if source is None:
            raise AdminError("not_found")
        if source.status == "running":
            return source
        source.status = "queued"
        source.stage = "idle"
        source.error_code = None
        await self._session.commit()
        await enqueue_wakeup(source.id)
        return source

    async def delete_source(self, source_id: UUID) -> None:
        source = await self._session.get(KbSource, source_id)
        if source is None:
            raise AdminError("not_found")
        # Composite FKs are NO ACTION; clear dependents before the source row.
        snapshot_ids = select(KbSnapshot.id).where(KbSnapshot.source_id == source_id)
        page_ids = select(KbPage.id).where(KbPage.source_id == source_id)
        await self._session.execute(delete(KbPageJob).where(KbPageJob.source_id == source_id))
        await self._session.execute(
            delete(KbPageLlmExtract).where(KbPageLlmExtract.page_id.in_(page_ids))
        )
        await self._session.execute(
            delete(KbChunk).where(
                (KbChunk.snapshot_id.in_(snapshot_ids)) | (KbChunk.page_id.in_(page_ids))
            )
        )
        await self._session.execute(delete(KbSnapshot).where(KbSnapshot.source_id == source_id))
        await self._session.execute(delete(KbPage).where(KbPage.source_id == source_id))
        await self._session.execute(
            delete(KbSmokeAssertion).where(KbSmokeAssertion.source_id == source_id)
        )
        await self._session.delete(source)
        await self._session.commit()
        clear_units_cache()

    async def list_pages(self, source_id: UUID) -> list[KbPage]:
        source = await self._session.get(KbSource, source_id)
        if source is None:
            raise AdminError("not_found")
        result = await self._session.execute(
            select(KbPage).where(KbPage.source_id == source_id).order_by(KbPage.url)
        )
        return list(result.scalars().all())

    async def get_page(self, page_id: UUID) -> tuple[KbPage, list[KbChunk]]:
        page = await self._session.get(KbPage, page_id)
        if page is None:
            raise AdminError("not_found")
        result = await self._session.execute(
            select(KbChunk)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .where(KbChunk.page_id == page.id, KbSnapshot.state == "live")
            .order_by(KbChunk.ordinal, KbChunk.id)
        )
        return page, list(result.scalars().all())

    async def patch_page(self, page_id: UUID, *, enabled: bool) -> KbPage:
        page = await self._session.get(KbPage, page_id)
        if page is None:
            raise AdminError("not_found")
        page.enabled = enabled
        result = await self._session.execute(select(KbChunk).where(KbChunk.page_id == page.id))
        for chunk in result.scalars().all():
            chunk.enabled = enabled
        await self._session.commit()
        return page

    async def list_snapshots(self, source_id: UUID) -> list[KbSnapshot]:
        source = await self._session.get(KbSource, source_id)
        if source is None:
            raise AdminError("not_found")
        return await KbSnapshotRepository(self._session).list_for_source(source_id)

    async def latest_snapshot(self, source_id: UUID) -> KbSnapshot | None:
        rows = await KbSnapshotRepository(self._session).list_for_source(source_id)
        return rows[0] if rows else None

    async def status_snapshot(self, source_id: UUID) -> KbSnapshot | None:
        rows = await KbSnapshotRepository(self._session).list_for_source(source_id)
        for state in ("building", "validated"):
            match = next((row for row in rows if row.state == state), None)
            if match is not None:
                return match
        live = next((row for row in rows if row.state == "live"), None)
        if live is not None:
            return live
        return rows[0] if rows else None

    async def diff_snapshots(
        self, source_id: UUID, from_id: UUID | None, to_id: UUID | None
    ) -> dict:
        source = await self._session.get(KbSource, source_id)
        if source is None:
            raise AdminError("not_found")
        repo = KbSnapshotRepository(self._session)
        snapshots = await repo.list_for_source(source_id)
        live = next((row for row in snapshots if row.state == "live"), None)
        previous = next((row for row in snapshots if row.state == "superseded"), None)
        start = from_id or (previous.id if previous is not None else None)
        end = to_id or (live.id if live is not None else None)
        if start is None or end is None:
            return {"added": [], "changed": [], "removed": []}
        before = await self._units_for_snapshot(start)
        after = await self._units_for_snapshot(end)
        before_map = {item["key"]: item for item in before}
        after_map = {item["key"]: item for item in after}
        added = [after_map[key] for key in after_map if key not in before_map]
        removed = [before_map[key] for key in before_map if key not in after_map]
        changed = []
        for key in before_map:
            if (
                key in after_map
                and before_map[key]["answer_verbatim"] != after_map[key]["answer_verbatim"]
            ):
                changed.append({"before": before_map[key], "after": after_map[key]})
        return {"added": added, "changed": changed, "removed": removed}

    async def rollback_source(self, source_id: UUID) -> KbSnapshot:
        source = await self._session.get(KbSource, source_id)
        if source is None:
            raise AdminError("not_found")
        previous = await KbSnapshotRepository(self._session).previous_superseded(source_id)
        if previous is None:
            raise AdminError("not_found")
        from app.services.kb_snapshot import promote

        await promote(self._session, previous.id)
        await self._session.commit()
        await self._session.refresh(previous)
        return previous

    async def _units_for_snapshot(self, snapshot_id: UUID) -> list[dict]:
        result = await self._session.execute(
            select(KbChunk).where(KbChunk.snapshot_id == snapshot_id).order_by(KbChunk.ordinal)
        )
        units = []
        seen: set[str] = set()
        for chunk in result.scalars().all():
            key = f"{chunk.canonical_question or chunk.heading}::{chunk.answer_verbatim}"
            if key in seen:
                continue
            seen.add(key)
            units.append(
                {
                    "key": key,
                    "kind": chunk.kind,
                    "canonical_question": chunk.canonical_question,
                    "heading": chunk.heading,
                    "answer_verbatim": chunk.answer_verbatim,
                    "display_locator": chunk.display_locator,
                }
            )
        return units
