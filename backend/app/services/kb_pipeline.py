from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session_maker
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.site import Site
from app.repositories.kb_page_job_repo import KbPageJobRepository
from app.repositories.kb_page_repo import KbPageRepository
from app.services.kb_backoff import classify_error, next_run_at, should_dead_letter
from app.services.kb_crawl import (
    FetchError,
)
from app.services.kb_embedder import Embedder, FakeEmbedder, OversizeChunkError
from app.services.kb_extract import extract_html
from app.services.kb_extract.text import visible_copy
from app.services.kb_extract.types import EvidenceUnit
from app.services.kb_fetcher import FetchResult, LazyPageCrawler, fetch_page
from app.services.kb_host_limiter import HostLimiter
from app.services.kb_ingest_chunks import _clean_units, _persist_chunks, _prepare_chunks
from app.services.kb_ingest_discovery import _planned_urls
from app.services.kb_ingest_publish import _fail_empty
from app.services.kb_ingest_publish import _finish_ingest as _finish_ingest
from app.services.kb_ingest_state import (
    _bump_source,
    _content_fingerprint,
    _fail_page,
    _pg_safe,
    _record_job_event,
    _stage_error_code,
    _sync_status,
)
from app.services.kb_snapshot import begin_snapshot
from app.settings import get_settings

log = structlog.get_logger("kb_pipeline")


async def run_ingest(
    session: AsyncSession,
    source_id: UUID,
    embedder: Embedder | None = None,
    fetch=None,
    llm_client=None,
) -> None:
    source = await session.get(KbSource, source_id)
    if source is None:
        return
    await session.refresh(
        source,
        attribute_names=[
            "pages_discovered",
            "pages_fetched",
            "pages_extracted",
            "pages_embedded",
            "pages_failed",
            "pages_skipped_unchanged",
        ],
    )
    site = await session.get(Site, source.site_id)
    if site is None:
        return
    now = datetime.now(UTC)
    retry_urls = list(source.retry_urls or [])
    source.retry_urls = []
    source.status = "running"
    source.stage = "discovering"
    source.error_code = None
    source.last_error_code = None
    source.last_run_started_at = now
    source.pages_discovered = 0
    source.pages_fetched = 0
    source.pages_extracted = 0
    source.pages_embedded = 0
    source.pages_failed = 0
    source.pages_skipped_unchanged = 0
    await session.commit()
    snapshot_id = await begin_snapshot(session, source.id)
    worker = embedder or FakeEmbedder()
    if source.source_kind == "text":
        await _run_text_ingest(session, source, snapshot_id, worker, llm_client)
        return
    await _run_website_ingest(
        session, source, site, snapshot_id, worker, fetch, llm_client, retry_urls
    )


async def _run_website_ingest(
    session: AsyncSession,
    source: KbSource,
    site: Site,
    snapshot_id: UUID,
    worker: Embedder,
    fetch,
    llm_client,
    retry_urls: list[str],
) -> None:
    from app.services.kb_crawl import fetch_html as http_fetch
    from app.services.kb_ingest import allowed_hosts_for

    hosts = allowed_hosts_for(site, source.start_url)
    robots: dict[str, str | None] = {}
    seen: set[str] = set()
    extra_urls: list[str] = []
    pending: list[dict] = []
    discover_fetch = fetch if fetch is not None else http_fetch
    limiter = HostLimiter(get_settings().kb_ingest_host_delay_ms)
    db_lock = asyncio.Lock()
    robots_lock = asyncio.Lock()
    page_sem = asyncio.Semaphore(max(1, get_settings().kb_ingest_page_concurrency))

    planned = (
        retry_urls
        if retry_urls
        else await _planned_urls(source, site, hosts, discover_fetch, robots)
    )
    source.stage = "processing"
    _sync_status(source)
    await session.commit()
    crawler_session = LazyPageCrawler(hosts) if fetch is None else None
    crawler = crawler_session.fetch if crawler_session is not None else None

    async def handle(url: str) -> None:
        async with page_sem:
            async with session_maker()() as page_session:
                page_source = await page_session.get(KbSource, source.id)
                page_site = await page_session.get(Site, site.id)
                if page_source is None or page_site is None:
                    return
                page_jobs = KbPageJobRepository(page_session)
                try:
                    item = await _process_url(
                        page_session,
                        page_source,
                        page_site,
                        url,
                        hosts,
                        fetch,
                        extra_urls,
                        robots,
                        seen,
                        snapshot_id,
                        worker,
                        page_jobs,
                        llm_client,
                        limiter,
                        db_lock,
                        robots_lock,
                        crawler,
                    )
                except Exception as exc:
                    log.info(
                        "kb_stage",
                        source_id=str(source.id),
                        stage="process",
                        state_to="failed",
                        error_code=type(exc).__name__,
                    )
                    async with db_lock:
                        page = await KbPageRepository(page_session).get_for_source_url(
                            page_source.id, url
                        )
                        job = (
                            await page_jobs.get_for_page_snapshot(page.id, snapshot_id)
                            if page is not None
                            else None
                        )
                        if page is not None and job is not None and job.state != "dead_letter":
                            await _fail_page(
                                page_session,
                                page_source,
                                page,
                                job,
                                _stage_error_code(job.stage),
                                type(exc).__name__,
                            )
                        else:
                            await _bump_source(page_session, page_source, "pages_failed")
                            page_source.last_error_code = "ingest"
                            await page_session.commit()
                    return
                if item:
                    async with db_lock:
                        pending.append(item)

    try:
        frontier = planned
        while frontier and len(seen) < source.max_pages:
            await _run_page_group(handle, frontier[: source.max_pages - len(seen)])
            if source.mode != "prefix":
                break
            remaining = source.max_pages - len(seen)
            frontier = [url for url in extra_urls if url not in seen][:remaining]
    finally:
        if crawler_session is not None:
            await crawler_session.aclose()
    source.pages_discovered = len(seen)
    await _finish_ingest(
        session,
        source,
        snapshot_id,
        pending,
        partial_run=bool(retry_urls),
    )


async def _run_text_ingest(
    session: AsyncSession,
    source: KbSource,
    snapshot_id: UUID,
    worker: Embedder,
    llm_client,
) -> None:
    title = (source.display_name or "").strip()
    body = (source.manual_text or "").strip()
    if not title or not body:
        await _fail_empty(session, source, snapshot_id)
        return
    source.stage = "processing"
    source.pages_discovered = 1
    _sync_status(source)
    page = await _ensure_page(session, source, source.start_url)
    if page is None:
        await _fail_empty(session, source, snapshot_id)
        return
    started = datetime.now(UTC)
    jobs = KbPageJobRepository(session)
    job = await jobs.upsert(source_id=source.id, page_id=page.id, snapshot_id=snapshot_id)
    job.state = "running"
    job.stage = "fetch"
    job.started_at = started
    job.attempts = 1
    page.processing_status = "fetching"
    _record_job_event(job, "fetch", "running", renderer="manual")
    await session.commit()
    digest = hashlib.sha256(f"{title}\0{body}".encode()).hexdigest()
    result = FetchResult(
        url=source.start_url,
        status=200,
        html="",
        markdown=body,
        content_sha256=digest,
        renderer="manual",
        title=title,
    )
    fingerprint = _content_fingerprint(digest)
    previous_hash = page.content_sha256
    job.stage = "extract"
    _record_job_event(job, "fetch", "done", renderer="manual")
    await _bump_source(session, source, "pages_fetched")
    baseline = await session.scalar(
        select(KbSnapshot)
        .where(KbSnapshot.source_id == source.id, KbSnapshot.state == "live")
        .order_by(KbSnapshot.created_at.desc())
    )
    if (
        baseline is not None
        and previous_hash
        and previous_hash == fingerprint
        and not await _has_generated_nonfaq_aliases(session, page.id, baseline.id)
    ):
        pending = await _mark_page_unchanged(session, source, page, job, source.start_url, result)
        await _finish_ingest(session, source, snapshot_id, [pending])
        return
    if llm_client is None or not hasattr(llm_client, "structure_text"):
        await _fail_page(session, source, page, job, "llm_extract")
        await _finish_ingest(session, source, snapshot_id, [])
        return
    page.processing_status = "llm_extracting"
    job.stage = "llm_extract"
    _record_job_event(job, "llm_extract", "running")
    await session.commit()
    try:
        structured = await llm_client.structure_text(title, body)
    except Exception as exc:
        await _fail_page(session, source, page, job, "llm_extract", str(exc))
        await _finish_ingest(session, source, snapshot_id, [])
        return
    pending = await _persist_extracted(
        session,
        source,
        source.start_url,
        source.start_url,
        result,
        snapshot_id,
        worker,
        page,
        job,
        structured.units,
        asyncio.Lock(),
        started,
    )
    await _finish_ingest(session, source, snapshot_id, [pending] if pending else [])


async def _run_page_group(handle, urls: list[str]) -> None:
    if not urls:
        return
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            tg.create_task(handle(url))


async def _process_url(
    session: AsyncSession,
    source: KbSource,
    site: Site,
    url: str,
    hosts: set[str],
    fetch,
    extra_urls: list[str],
    robots: dict[str, str | None],
    seen: set[str],
    snapshot_id: UUID,
    worker: Embedder,
    jobs: KbPageJobRepository,
    llm_client,
    limiter: HostLimiter,
    lock: asyncio.Lock,
    robots_lock: asyncio.Lock,
    crawler=None,
) -> dict | None:
    from app.services.kb_crawl import fetch_html as http_fetch
    from app.services.kb_ingest import (
        CanonicalError,
        _url_allowed_by_source_rules,
        canonical_fetch_url,
        host_allowed,
    )
    from app.services.kb_ingest import (
        robots_body as robots_body_fn,
    )

    started = datetime.now(UTC)
    async with lock:
        try:
            fetch_url = canonical_fetch_url(url)
        except CanonicalError:
            log.info("kb_stage", source_id=str(source.id), stage="fetch", state_to="dead_letter")
            return None
        if fetch_url in seen:
            return None
        seen.add(fetch_url)
        if not host_allowed(fetch_url, site, source.start_url):
            return None
        if not _url_allowed_by_source_rules(fetch_url, source):
            return None
    async with robots_lock:
        robots_body = await robots_body_fn(
            fetch_url, hosts, fetch if fetch is not None else http_fetch, robots
        )
    if robots_body is not None and not _robots_ok(fetch_url, robots_body):
        return None

    async with lock:
        page = await _ensure_page(session, source, fetch_url)
        if page is None:
            await _bump_source(session, source, "pages_failed")
            source.last_error_code = "url_overlap"
            await session.commit()
            return None
        job = await jobs.upsert(source_id=source.id, page_id=page.id, snapshot_id=snapshot_id)
        job.state = "running"
        job.stage = "fetch"
        job.started_at = started
        _record_job_event(job, "fetch", "running")
        page.processing_status = "fetching"
        await session.commit()

    result = await _fetch_with_retry(
        session, source, page, job, fetch_url, hosts, fetch, limiter, lock, crawler
    )
    return await _after_fetch(
        session,
        source,
        url,
        fetch_url,
        result,
        extra_urls,
        seen,
        snapshot_id,
        worker,
        page,
        job,
        llm_client,
        lock,
        started,
    )


def _robots_ok(url: str, robots_body: str) -> bool:
    from app.services.kb_crawl import robots_allows

    return robots_allows(url, robots_body)


async def _after_fetch(
    session: AsyncSession,
    source: KbSource,
    url: str,
    fetch_url: str,
    result: FetchResult | None,
    extra_urls: list[str],
    seen: set[str],
    snapshot_id: UUID,
    worker: Embedder,
    page: KbPage,
    job: KbPageJob,
    llm_client,
    lock: asyncio.Lock,
    started: datetime,
) -> dict | None:
    html = result.html if result is not None else None
    async with lock:
        if html is None:
            _log_fetch_failure(source, page, snapshot_id, job, started)
            return None
        raw_digest = result.content_sha256
        digest = _content_fingerprint(raw_digest)
        markdown = result.markdown
        await _bump_source(session, source, "pages_fetched")
        previous_hash = page.content_sha256
        page.processing_status = "fetched"
        job.stage = "extract"
        _record_job_event(job, "fetch", "done", renderer=result.renderer)
        _record_job_event(job, "extract", "running", renderer=result.renderer)
        if source.mode == "prefix":
            _collect_prefix_links(html, result.url, source, extra_urls, seen, result.links)
        baseline = await session.scalar(
            select(KbSnapshot)
            .where(
                KbSnapshot.source_id == source.id,
                KbSnapshot.state == "live",
            )
            .order_by(KbSnapshot.created_at.desc())
        )
        if (
            baseline is not None
            and previous_hash
            and previous_hash == digest
            and not await _has_generated_nonfaq_aliases(session, page.id, baseline.id)
        ):
            return await _mark_page_unchanged(session, source, page, job, fetch_url, result)
        page.processing_status = "extracting"
        await session.commit()
    structured = hasattr(llm_client, "structure_page")
    units = [] if structured else extract_html(html, url=url, markdown=markdown)
    async with lock:
        page.processing_status = "llm_extracting"
        job.stage = "llm_extract"
        _record_job_event(job, "llm_extract", "running")
        await session.commit()
    cleaned = await _clean_units(
        session,
        page,
        raw_digest,
        units,
        llm_client,
        lock,
        crawl_text=(markdown or visible_copy(html)) if structured else None,
        crawl_title=result.title or "Crawled page",
        crawl_metadata=result.metadata,
    )
    return await _persist_extracted(
        session,
        source,
        url,
        fetch_url,
        result,
        snapshot_id,
        worker,
        page,
        job,
        cleaned,
        lock,
        started,
    )


async def _has_generated_nonfaq_aliases(
    session: AsyncSession, page_id: UUID, live_snapshot_id: UUID
) -> bool:
    contaminated = await session.scalar(
        select(KbChunk.id).where(
            KbChunk.page_id == page_id,
            KbChunk.snapshot_id == live_snapshot_id,
            KbChunk.kind != "faq",
            KbChunk.aliases != [],
        )
    )
    return contaminated is not None


def _log_fetch_failure(
    source: KbSource, page: KbPage, snapshot_id: UUID, job: KbPageJob, started: datetime
) -> None:
    duration_ms = round((datetime.now(UTC) - started).total_seconds() * 1000)
    log.info(
        "kb_stage",
        source_id=str(source.id),
        page_id=str(page.id),
        snapshot_id=str(snapshot_id),
        stage="fetch",
        state_from="running",
        state_to=job.state,
        attempt=job.attempts,
        duration_ms=duration_ms,
        error_class=classify_error(job.last_error_code or "http"),
        error_code=job.last_error_code,
    )


def _collect_prefix_links(
    html: str,
    fetch_url: str,
    source: KbSource,
    extra_urls: list[str],
    seen: set[str],
    crawler_links: tuple[str, ...] = (),
) -> None:
    from app.services.kb_ingest import (
        CanonicalError,
        _links_from,
        _same_prefix,
        _url_allowed_by_source_rules,
        canonical_fetch_url,
    )

    discovered = list(crawler_links) + _links_from(html, fetch_url)
    for raw in discovered:
        try:
            link = canonical_fetch_url(raw)
        except CanonicalError:
            continue
        if link in extra_urls or link in seen:
            continue
        if not _url_allowed_by_source_rules(link, source):
            continue
        if _same_prefix(link, source.start_url):
            extra_urls.append(link)


async def _mark_page_unchanged(
    session: AsyncSession,
    source: KbSource,
    page: KbPage,
    job: KbPageJob,
    fetch_url: str,
    result: FetchResult,
) -> dict:
    page.processing_status = "unchanged"
    page.last_success_at = datetime.now(UTC)
    job.state = "unchanged"
    job.stage = "persist"
    job.finished_at = datetime.now(UTC)
    _record_job_event(job, "persist", "unchanged", renderer=result.renderer)
    await _bump_source(session, source, "pages_skipped_unchanged")
    await session.commit()
    return {
        "fetch_url": fetch_url,
        "digest": _content_fingerprint(result.content_sha256),
        "token_estimate": 0,
        "copy_from_live": True,
        "page_id": page.id,
        "raw_html": result.html,
        "markdown": (result.markdown or "").strip() or visible_copy(result.html),
        "http_status": result.status,
        "renderer": result.renderer,
    }


async def _persist_extracted(
    session: AsyncSession,
    source: KbSource,
    url: str,
    fetch_url: str,
    result: FetchResult,
    snapshot_id: UUID,
    worker: Embedder,
    page: KbPage,
    job: KbPageJob,
    units: list[EvidenceUnit],
    lock: asyncio.Lock,
    started: datetime,
) -> dict | None:
    from app.services.kb_ingest import display_locator

    digest = _content_fingerprint(result.content_sha256)

    async with lock:
        if not units:
            page.processing_status = "failed"
            page.skip_reason = "empty"
            page.failure_reason = "empty"
            job.state = "dead_letter"
            job.last_error_code = "empty"
            job.finished_at = datetime.now(UTC)
            _record_job_event(job, "extract", "dead_letter", error_code="empty")
            await _bump_source(session, source, "pages_failed")
            await session.commit()
            return None
        await _bump_source(session, source, "pages_extracted")
        page.processing_status = "embedding"
        job.stage = "embed"
        _record_job_event(job, "embed", "running", renderer=result.renderer)
        await session.commit()
    try:
        pieces, vectors, token_estimate = await _prepare_chunks(units, worker)
    except OversizeChunkError:
        async with lock:
            await _fail_page(session, source, page, job, "oversize")
        return None
    except Exception:
        async with lock:
            await _fail_page(session, source, page, job, "embed")
        return None
    async with lock:
        try:
            await _persist_chunks(session, source, page, snapshot_id, pieces, vectors)
        except Exception:
            await session.rollback()
            current_source = await session.get(KbSource, source.id)
            current_page = await session.get(KbPage, page.id)
            current_job = await session.get(KbPageJob, job.id)
            if current_source is not None and current_page is not None and current_job is not None:
                await _fail_page(session, current_source, current_page, current_job, "persist")
            return None
        page.processing_status = "ready"
        page.last_success_at = datetime.now(UTC)
        job.stage = "persist"
        job.state = "done"
        job.finished_at = datetime.now(UTC)
        _record_job_event(job, "persist", "done", renderer=result.renderer)
        await _bump_source(session, source, "pages_embedded")
        await session.commit()
        log.info(
            "kb_stage",
            source_id=str(source.id),
            page_id=str(page.id),
            snapshot_id=str(snapshot_id),
            stage="persist",
            state_from="running",
            state_to="done",
            attempt=job.attempts,
            duration_ms=round((datetime.now(UTC) - started).total_seconds() * 1000),
        )
        return {
            "fetch_url": fetch_url,
            "digest": digest,
            "token_estimate": token_estimate,
            "page_id": page.id,
            "title": _pg_safe(result.title or units[0].heading or "Untitled"),
            "content_text": _pg_safe(
                "\n\n".join(unit.answer_verbatim for unit in units if unit.enabled)
            ),
            "structured": any(unit.structured_text is not None for unit in units),
            "display_locator": display_locator(url) or units[0].display_locator,
            "raw_html": result.html,
            "markdown": (result.markdown or "").strip() or visible_copy(result.html),
            "http_status": result.status,
            "renderer": result.renderer,
        }


async def _ensure_page(session: AsyncSession, source: KbSource, url: str) -> KbPage | None:
    pages = KbPageRepository(session)
    page = await pages.get_for_source_url(source.id, url)
    if page is not None:
        page.processing_status = "pending"
        page.failure_reason = None
        return page
    overlap = await session.scalar(
        select(KbPage).where(KbPage.site_id == source.site_id, KbPage.url == url)
    )
    if overlap is not None:
        log.info(
            "kb_stage",
            source_id=str(source.id),
            stage="fetch",
            state_to="skipped",
            error_code="url_overlap",
        )
        return None
    page = KbPage(
        source_id=source.id,
        site_id=source.site_id,
        url=url,
        citation_url=None if source.source_kind == "text" else url,
        title="Pending",
        content_text="",
        content_sha256="",
        http_status=0,
        enabled=True,
        processing_status="pending",
    )
    session.add(page)
    await session.flush()
    return page


async def _fetch_with_retry(
    session: AsyncSession,
    source: KbSource,
    page: KbPage,
    job: KbPageJob,
    url: str,
    hosts: set[str],
    fetch,
    limiter: HostLimiter,
    lock: asyncio.Lock,
    crawler=None,
) -> FetchResult | None:
    settings = get_settings()
    last_code = "http"
    max_attempts = job.max_attempts
    for attempt in range(1, max_attempts + 1):
        await limiter.wait_url(url)
        try:
            result = await fetch_page(url, hosts, fetch=fetch, crawler=crawler)
            async with lock:
                job.attempts = attempt
                job.renderer = result.renderer
                job.http_status = result.status
            return result
        except FetchError as exc:
            last_code = exc.code
            error_class = classify_error(exc.code)
            async with lock:
                job.attempts = attempt
                job.last_error_code = exc.code
                job.next_run_at = next_run_at(datetime.now(UTC), attempt)
                if (
                    should_dead_letter(error_class, attempt, max_attempts)
                    or error_class != "transient"
                ):
                    await _fail_page(session, source, page, job, exc.code)
                    return None
                job.state = "transient_failed"
                _record_job_event(job, "fetch", "transient_failed", error_code=exc.code)
                await session.commit()
            if settings.kb_ingest_retry_sleep > 0:
                await asyncio.sleep(settings.kb_ingest_retry_sleep)
    async with lock:
        await _fail_page(session, source, page, job, last_code)
    return None
