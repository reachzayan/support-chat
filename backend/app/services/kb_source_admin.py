from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_page_llm_extract import KbPageLlmExtract
from app.models.kb_smoke_assertion import KbSmokeAssertion
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource, general_tab_id_for
from app.models.site import Site
from app.models.user import User
from app.repositories.kb_snapshot_repo import KbSnapshotRepository
from app.repositories.kb_source_repo import KbSourceRepository
from app.services.kb_embedder import configured_embedder_id
from app.services.kb_ingest import CanonicalError, canonical_fetch_url, enqueue_wakeup, host_allowed
from app.services.site_admin import AdminError

SAMPLESITE_SMOKE = ["24-48", "MRO", "rapid"]


def general_tab_id(source_id: UUID) -> UUID:
    return general_tab_id_for(source_id)


def _origin_count():
    return func.coalesce(func.jsonb_array_length(KbChunk.origin_urls), 0)


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
        host_seeds = seed_urls if seed_urls else [start_url]
        self._assert_seed_hosts(self._normalized_seed_urls(host_seeds), site, start_url)
        urls = self._normalized_seed_urls(raw_seeds)
        resolved_mode = mode
        existing = await KbSourceRepository(self._session).get_by_site_start_url(site_id, start_url)
        if existing is not None:
            if existing.status == "running":
                raise AdminError("busy")
            already_queued = existing.status == "queued"
            existing.mode = resolved_mode
            existing.seed_urls = urls
            existing.status = "queued"
            existing.stage = "idle"
            existing.error_code = None
            existing.enabled = True
            await self._ensure_samplesite_smoke(existing)
            await self._session.commit()
            if not already_queued:
                await enqueue_wakeup(existing.id)
            return existing
        overlap = await self._session.scalar(
            select(KbPage.id).where(KbPage.site_id == site_id, KbPage.url == start_url)
        )
        if overlap is not None:
            raise AdminError("overlap")
        source = KbSource(
            site_id=site_id,
            start_url=start_url,
            mode=resolved_mode,
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

    async def create_text_source(
        self,
        site_id: UUID,
        admin: User,
        *,
        title: str,
        body: str,
    ) -> KbSource:
        site = await self._session.get(Site, site_id)
        if site is None:
            raise AdminError("not_found")
        title, body = self._clean_manual_text(title, body)
        source_id = uuid4()
        source = KbSource(
            id=source_id,
            site_id=site_id,
            start_url=f"kb-text://{source_id}",
            mode="list",
            seed_urls=[],
            max_pages=1,
            status="queued",
            embedder_id=configured_embedder_id(),
            source_kind="text",
            display_name=title,
            manual_text=body,
            created_by=admin.id,
            enabled=True,
        )
        self._session.add(source)
        await self._session.commit()
        await enqueue_wakeup(source.id)
        return source

    @staticmethod
    def _clean_manual_text(title: str, body: str) -> tuple[str, str]:
        clean_title = title.replace("\x00", "").strip()
        clean_body = body.replace("\x00", "").strip()
        if not clean_title or not clean_body:
            raise AdminError("invalid")
        if len(clean_title) > 300 or len(clean_body) > 40_000:
            raise AdminError("too_large")
        return clean_title, clean_body

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
            urls.append(fetch_url)
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

    async def patch_source(
        self,
        source_id: UUID,
        *,
        enabled: bool | None,
        title: str | None = None,
        body: str | None = None,
    ) -> KbSource:
        source = await self._session.get(KbSource, source_id)
        if source is None:
            raise AdminError("not_found")
        if enabled is not None:
            source.enabled = enabled
        editing_text = title is not None or body is not None
        text_changed = False
        if editing_text:
            if source.source_kind != "text":
                raise AdminError("invalid")
            if source.status == "running":
                raise AdminError("busy")
            clean_title, clean_body = self._clean_manual_text(
                title if title is not None else source.display_name or "",
                body if body is not None else source.manual_text or "",
            )
            if (clean_title, clean_body) != (source.display_name, source.manual_text):
                text_changed = True
                source.display_name = clean_title
                source.manual_text = clean_body
                source.status = "queued"
                source.stage = "idle"
                source.error_code = None
        await self._session.commit()
        if text_changed:
            await enqueue_wakeup(source.id)
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

    async def retry_page(self, page_id: UUID) -> KbSource:
        page = await self._session.get(KbPage, page_id)
        if page is None:
            raise AdminError("not_found")
        source = await self._session.get(KbSource, page.source_id)
        if source is None:
            raise AdminError("not_found")
        if source.status == "running":
            raise AdminError("busy")
        source.retry_urls = [page.url]
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

    async def list_pages(self, source_id: UUID) -> list[tuple[KbPage, int]]:
        source = await self._session.get(KbSource, source_id)
        if source is None:
            raise AdminError("not_found")
        live_chunk_count = (
            select(func.count(KbChunk.id))
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .where(
                KbChunk.page_id == KbPage.id,
                KbSnapshot.state == "live",
                _origin_count() < 2,
            )
            .correlate(KbPage)
            .scalar_subquery()
        )
        result = await self._session.execute(
            select(KbPage, live_chunk_count)
            .where(KbPage.source_id == source_id)
            .order_by(KbPage.url)
        )
        rows = [(page, int(chunk_count)) for page, chunk_count in result.all()]
        shared_count = await self._shared_chunk_count(source_id)
        if len(rows) > 1 and shared_count > 0:
            return [(self._general_page(source), shared_count), *rows]
        return rows

    async def get_page(self, page_id: UUID) -> tuple[KbPage, list[KbChunk]]:
        page = await self._session.get(KbPage, page_id)
        if page is not None:
            chunks = await self._live_chunks(
                KbChunk.page_id == page.id,
                shared=False,
            )
            return page, chunks
        source = await self._source_for_general_tab(page_id)
        if source is None:
            raise AdminError("not_found")
        chunks = await self._live_chunks(
            KbPage.source_id == source.id,
            shared=True,
        )
        return self._general_page(source), chunks

    async def patch_page(self, page_id: UUID, *, enabled: bool) -> KbPage:
        page = await self._session.get(KbPage, page_id)
        if page is None:
            raise AdminError("not_found")
        page.enabled = enabled
        await self._session.commit()
        return page

    async def patch_chunk(self, chunk_id: UUID, *, enabled: bool) -> KbChunk:
        result = await self._session.execute(
            select(KbChunk)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .where(KbChunk.id == chunk_id, KbSnapshot.state == "live")
        )
        chunk = result.scalar_one_or_none()
        if chunk is None:
            if await self._session.get(KbChunk, chunk_id) is None:
                raise AdminError("not_found")
            raise AdminError("stale")
        chunk.enabled = enabled
        await self._session.commit()
        return chunk

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
            if end is None:
                return {"added": [], "changed": [], "removed": []}
            after = await self._units_for_snapshot(end)
            return {"added": after, "changed": [], "removed": []}
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

    def _general_page(self, source: KbSource) -> KbPage:
        return KbPage(
            id=general_tab_id(source.id),
            source_id=source.id,
            site_id=source.site_id,
            url=source.start_url,
            citation_url=source.start_url,
            title="General",
            content_text="",
            content_sha256="",
            http_status=200,
            enabled=True,
            processing_status="ready",
        )

    async def _source_for_general_tab(self, page_id: UUID) -> KbSource | None:
        return await self._session.scalar(
            select(KbSource).where(KbSource.general_tab_id == page_id)
        )

    async def _shared_chunk_count(self, source_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count(KbChunk.id))
            .join(KbPage, KbPage.id == KbChunk.page_id)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .where(
                KbPage.source_id == source_id,
                KbSnapshot.state == "live",
                _origin_count() >= 2,
            )
        )
        return int(result.scalar_one() or 0)

    async def _live_chunks(self, *filters, shared: bool) -> list[KbChunk]:
        origin_filter = _origin_count() >= 2 if shared else _origin_count() < 2
        result = await self._session.execute(
            select(KbChunk)
            .join(KbPage, KbPage.id == KbChunk.page_id)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
            .where(*filters, KbSnapshot.state == "live", origin_filter)
            .order_by(KbChunk.heading, KbChunk.ordinal, KbChunk.id)
        )
        return list(result.scalars().all())

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
            select(KbChunk)
            .where(KbChunk.snapshot_id == snapshot_id)
            .order_by(KbChunk.page_id, KbChunk.ordinal, KbChunk.id)
        )
        units: list[dict] = []
        by_key: dict[str, dict] = {}
        for chunk in result.scalars().all():
            key = f"{chunk.page_id}::{chunk.canonical_question or chunk.heading}"
            existing = by_key.get(key)
            if existing is not None:
                existing["answer_verbatim"] = (
                    f"{existing['answer_verbatim']}\n\n{chunk.answer_verbatim}"
                )
                continue
            item = {
                "key": key,
                "kind": chunk.kind,
                "canonical_question": chunk.canonical_question,
                "heading": chunk.heading,
                "answer_verbatim": chunk.answer_verbatim,
                "display_locator": chunk.display_locator,
            }
            by_key[key] = item
            units.append(item)
        return units
