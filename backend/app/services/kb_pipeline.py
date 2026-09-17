from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_page_llm_extract import KbPageLlmExtract
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.site import Site
from app.repositories.kb_page_job_repo import KbPageJobRepository
from app.repositories.kb_page_repo import KbPageRepository
from app.services.kb_backoff import classify_error, next_run_at, should_dead_letter
from app.services.kb_chunk import TextChunk, pack_chunks, split_chunks_for_embed
from app.services.kb_crawl import (
    FetchError,
    parse_sitemap_locs,
    sitemap_urls_from_robots,
)
from app.services.kb_embedder import Embedder, FakeEmbedder, OversizeChunkError, count_embed_tokens
from app.services.kb_extract import extract_html
from app.services.kb_extract.text import visible_copy
from app.services.kb_extract.types import EvidenceUnit
from app.services.kb_fetcher import FetchResult, LazyPageCrawler, fetch_page
from app.services.kb_host_limiter import HostLimiter
from app.services.kb_llm_extract import apply_cleaner
from app.services.kb_snapshot import begin_snapshot, fail, mark_unchanged, validate_snapshot
from app.services.kb_validate import PageEvidence, ValidationResult
from app.settings import get_settings

log = structlog.get_logger("kb_pipeline")
CONTENT_FINGERPRINT_VERSION = "haiku-page-v5"


def _content_fingerprint(raw_digest: str) -> str:
    return f"{CONTENT_FINGERPRINT_VERSION}:{get_settings().haiku_model}:{raw_digest}"


def _sync_status(source: KbSource) -> None:
    if source.stage in {"discovering", "processing", "validating", "promoting"}:
        source.status = "running"
    elif source.stage == "failed":
        source.status = "failed"
    elif source.stage in {"ready", "idle"}:
        source.status = "ready" if source.stage == "ready" else source.status


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
    jobs = KbPageJobRepository(session)
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
            try:
                item = await _process_url(
                    session,
                    source,
                    site,
                    url,
                    hosts,
                    fetch,
                    extra_urls,
                    robots,
                    seen,
                    snapshot_id,
                    worker,
                    jobs,
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
                    page = await KbPageRepository(session).get_for_source_url(source.id, url)
                    job = (
                        await jobs.get_for_page_snapshot(page.id, snapshot_id)
                        if page is not None
                        else None
                    )
                    if page is not None and job is not None and job.state != "dead_letter":
                        await _fail_page(
                            session,
                            source,
                            page,
                            job,
                            _stage_error_code(job.stage),
                            str(exc),
                        )
                    else:
                        await _bump_source(session, source, "pages_failed")
                        source.last_error_code = "ingest"
                        await session.commit()
                return
            if item:
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


async def _fail_empty(session: AsyncSession, source: KbSource, snapshot_id: UUID) -> None:
    await fail(session, snapshot_id, "empty")
    source.stage = "failed"
    source.status = "failed"
    source.error_code = "empty"
    source.last_error_code = "empty"
    source.last_run_finished_at = datetime.now(UTC)
    await session.commit()


async def _mark_unchanged(
    session: AsyncSession,
    source: KbSource,
    snapshot_id: UUID,
    pending: list[dict],
    content_hash: str,
) -> None:
    await mark_unchanged(session, snapshot_id, content_hash)
    await _apply_staged_pages(session, pending)
    source.stage = "ready"
    source.status = "ready"
    source.error_code = None
    source.page_count = len(pending)
    source.last_run_finished_at = datetime.now(UTC)
    await session.commit()


async def _finish_ingest(
    session: AsyncSession,
    source: KbSource,
    snapshot_id: UUID,
    pending: list[dict],
    *,
    partial_run: bool = False,
) -> None:
    if not pending and source.pages_failed > 0:
        await _fail_all_pages(session, source, snapshot_id)
        return
    if not pending and source.pages_embedded == 0 and source.pages_skipped_unchanged == 0:
        await _fail_empty(session, source, snapshot_id)
        return
    live = await session.scalar(
        select(KbSnapshot)
        .where(
            KbSnapshot.source_id == source.id,
            KbSnapshot.state == "live",
        )
        .order_by(KbSnapshot.created_at.desc())
    )
    if live is not None:
        await _carry_forward_failed_pages(session, source, snapshot_id, live.id, pending)
        if partial_run:
            await _carry_forward_unrequested_pages(session, live.id, pending)
    content_hash = _content_hash(pending)
    if (
        live is not None
        and live.content_hash == content_hash
        and source.pages_failed == 0
        and all(item.get("copy_from_live") for item in pending)
    ):
        await _mark_unchanged(session, source, snapshot_id, pending, content_hash)
        return
    if live is not None:
        await _copy_pending_live_chunks(session, source, live.id, snapshot_id, pending)
    await _stage_snapshot(session, snapshot_id, pending, content_hash)
    source.stage = "validating"
    _sync_status(source)
    staged_pages = {
        item["page_id"]: PageEvidence(
            id=item["page_id"],
            url=item["fetch_url"],
            raw_html=item.get("raw_html"),
            markdown=item.get("markdown"),
        )
        for item in pending
    }
    result = await validate_snapshot(session, snapshot_id, staged_pages)
    await _publish_validated_snapshot(session, source, snapshot_id, pending, result)


async def _publish_validated_snapshot(
    session: AsyncSession,
    source: KbSource,
    snapshot_id: UUID,
    pending: list[dict],
    result: ValidationResult,
) -> None:
    # Show precisely the published evidence, including per-chunk validation drops.
    retained = list(
        (
            await session.scalars(
                select(KbChunk)
                .where(KbChunk.snapshot_id == snapshot_id)
                .order_by(KbChunk.page_id, KbChunk.ordinal)
            )
        ).all()
    )
    for item in pending:
        if not item.get("copy_from_live"):
            item["content_text"] = "\n\n".join(
                chunk.body if item.get("structured") else chunk.answer_verbatim
                for chunk in retained
                if chunk.page_id == item["page_id"] and chunk.enabled
            )
    dropped_reasons = {item.page_id: item.reason for item in result.dropped}
    for item in pending:
        reason = dropped_reasons.get(item["page_id"])
        if reason:
            item["dropped"] = True
            item["drop_reason"] = reason
    await _record_validation_progress(session, snapshot_id, pending)
    if result.failed_rules:
        if not any(item.get("dropped") for item in pending):
            for item in pending:
                if not item.get("copy_from_live"):
                    item["dropped"] = True
                    item["drop_reason"] = result.failed_rules[0]
        await _apply_staged_pages(session, pending)
        source.stage = "failed"
        source.status = "failed"
        source.last_run_finished_at = datetime.now(UTC)
        await session.commit()
        return
    from app.services.kb_snapshot import promote

    await promote(session, snapshot_id)
    await _apply_staged_pages(session, pending)
    source.stage = "ready"
    source.status = "ready"
    source.error_code = None
    source.page_count = len({item["page_id"] for item in pending})
    source.last_run_finished_at = datetime.now(UTC)
    await session.commit()
    from app.services.full_context import clear_units_cache

    clear_units_cache()


async def _fail_all_pages(session: AsyncSession, source: KbSource, snapshot_id: UUID) -> None:
    await fail(session, snapshot_id, "page_failures")
    source.stage = "failed"
    source.status = "failed"
    source.error_code = "page_failures"
    source.last_error_code = "page_failures"
    source.last_run_finished_at = datetime.now(UTC)
    await session.commit()


async def _copy_pending_live_chunks(
    session: AsyncSession,
    source: KbSource,
    live_id: UUID,
    snapshot_id: UUID,
    pending: list[dict],
) -> None:
    for item in pending:
        if not item.get("copy_from_live"):
            continue
        page = await session.get(KbPage, item["page_id"])
        if page is None:
            continue
        copied, copied_tokens = await _copy_live_chunks(session, page, live_id, snapshot_id)
        if copied:
            item["token_estimate"] = copied_tokens
            if not item.get("preserve_failure") and not item.get("preserve_page_state"):
                source.pages_embedded += 1


async def _stage_snapshot(
    session: AsyncSession, snapshot_id: UUID, pending: list[dict], content_hash: str
) -> None:
    snapshot = await session.get(KbSnapshot, snapshot_id)
    if snapshot is None:
        return
    snapshot.content_hash = content_hash
    snapshot.token_estimate = sum(item.get("token_estimate", 0) for item in pending)


async def _record_validation_progress(
    session: AsyncSession, snapshot_id: UUID, pending: list[dict]
) -> None:
    for item in pending:
        if not item.get("dropped"):
            continue
        job = await session.scalar(
            select(KbPageJob).where(
                KbPageJob.page_id == item["page_id"],
                KbPageJob.snapshot_id == snapshot_id,
            )
        )
        if job is None:
            continue
        reason = str(item.get("drop_reason") or "validation")
        _record_job_event(job, "persist", "done", error_code=reason)


async def _apply_staged_pages(session: AsyncSession, pending: list[dict]) -> None:
    now = datetime.now(UTC)
    for item in pending:
        page = await session.get(KbPage, item["page_id"])
        if page is None:
            continue
        if item.get("preserve_failure") or item.get("preserve_page_state"):
            continue
        if item.get("dropped") and not item.get("copy_from_live"):
            reason = str(item.get("drop_reason") or "validation")
            page.markdown = item.get("markdown")
            if page.last_success_at is None:
                page.raw_html = item.get("raw_html")
                page.http_status = item.get("http_status", 200)
                page.content_sha256 = item["digest"]
                page.title = item["title"]
                page.content_text = item["content_text"]
                page.display_locator = item.get("display_locator")
            page.processing_status = "failed"
            page.skip_reason = reason
            page.failure_reason = reason
            continue
        page.raw_html = item.get("raw_html")
        page.markdown = item.get("markdown")
        page.http_status = item.get("http_status", 200)
        page.content_sha256 = item["digest"]
        if not item.get("copy_from_live"):
            page.title = item["title"]
            page.content_text = item["content_text"]
            page.display_locator = item.get("display_locator")
        if item.get("dropped") and not item.get("copy_from_live"):
            reason = str(item.get("drop_reason") or "validation")
            page.processing_status = "failed"
            page.skip_reason = reason
            page.failure_reason = reason
            continue
        page.processing_status = "unchanged" if item.get("copy_from_live") else "ready"
        page.skip_reason = None
        page.failure_reason = None
        page.last_success_at = now


async def _carry_forward_failed_pages(
    session: AsyncSession,
    source: KbSource,
    snapshot_id: UUID,
    live_id: UUID,
    pending: list[dict],
) -> None:
    pending_ids = {item["page_id"] for item in pending}
    failed_page_ids = set(
        (
            await session.scalars(
                select(KbPageJob.page_id).where(
                    KbPageJob.source_id == source.id,
                    KbPageJob.snapshot_id == snapshot_id,
                    KbPageJob.state == "dead_letter",
                )
            )
        ).all()
    )
    for page_id in failed_page_ids - pending_ids:
        has_live_chunks = await session.scalar(
            select(KbChunk.id).where(
                KbChunk.page_id == page_id,
                KbChunk.snapshot_id == live_id,
            )
        )
        page = await session.get(KbPage, page_id)
        if page is None or has_live_chunks is None:
            continue
        pending.append(
            {
                "fetch_url": page.url,
                "digest": page.content_sha256,
                "token_estimate": 0,
                "copy_from_live": True,
                "preserve_failure": True,
                "page_id": page.id,
                "raw_html": page.raw_html,
                "markdown": page.markdown,
                "http_status": page.http_status,
            }
        )


async def _carry_forward_unrequested_pages(
    session: AsyncSession, live_id: UUID, pending: list[dict]
) -> None:
    pending_ids = {item["page_id"] for item in pending}
    live_page_ids = set(
        (
            await session.scalars(
                select(KbChunk.page_id).where(KbChunk.snapshot_id == live_id).distinct()
            )
        ).all()
    )
    for page_id in live_page_ids - pending_ids:
        page = await session.get(KbPage, page_id)
        if page is None:
            continue
        pending.append(
            {
                "fetch_url": page.url,
                "digest": page.content_sha256,
                "token_estimate": 0,
                "copy_from_live": True,
                "preserve_page_state": True,
                "page_id": page.id,
                "raw_html": page.raw_html,
                "markdown": page.markdown,
                "http_status": page.http_status,
            }
        )


async def _run_page_group(handle, urls: list[str]) -> None:
    if not urls:
        return
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            tg.create_task(handle(url))


async def _planned_urls(source: KbSource, site: Site, hosts: set[str], fetch, robots) -> list[str]:
    from app.services.kb_ingest import _plan_urls

    if source.mode == "prefix":
        sitemap_urls = await _sitemap_seed_urls(source, site, hosts, fetch, robots)
        if sitemap_urls:
            return sitemap_urls[: source.max_pages]
    return _plan_urls(source)[: source.max_pages]


async def _sitemap_seed_urls(
    source: KbSource, site: Site, hosts: set[str], fetch, robots
) -> list[str]:
    from app.services.kb_ingest import robots_body

    host = urlparse(source.start_url).hostname
    candidates: list[str] = []
    robots_txt = await robots_body(source.start_url, hosts, fetch, robots) or ""
    candidates.extend(sitemap_urls_from_robots(robots_txt))
    if host:
        candidates.append(f"https://{host.casefold()}/sitemap.xml")
        candidates.append(f"https://{host.casefold()}/sitemap_index.xml")
    locs = await _expand_sitemap_locs(candidates, hosts, fetch)
    return _filter_sitemap_urls(locs, source, site)


async def _expand_sitemap_locs(candidates: list[str], hosts: set[str], fetch) -> list[str]:
    from app.services.kb_ingest import try_fetch

    locs: list[str] = []
    nested: list[str] = []
    seen: set[str] = set()
    for sitemap_url in candidates:
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        body = await try_fetch(sitemap_url, hosts, fetch)
        if not body:
            continue
        parsed = parse_sitemap_locs(body)
        if not parsed:
            continue
        for loc in parsed:
            if loc.rstrip("/").endswith(".xml"):
                nested.append(loc)
            else:
                locs.append(loc)
    for sitemap_url in nested:
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        body = await try_fetch(sitemap_url, hosts, fetch)
        if body:
            locs.extend(parse_sitemap_locs(body))
    return locs


def _filter_sitemap_urls(locs: list[str], source: KbSource, site: Site) -> list[str]:
    from app.services.kb_ingest import (
        CanonicalError,
        _url_allowed_by_source_rules,
        canonical_fetch_url,
        host_allowed,
    )

    filtered: list[str] = []
    for loc in locs:
        try:
            url = canonical_fetch_url(loc)
        except CanonicalError:
            continue
        if not host_allowed(url, site, source.start_url):
            continue
        if not _url_allowed_by_source_rules(url, source):
            continue
        if url not in filtered:
            filtered.append(url)
    return filtered


def _content_hash(pending: list[dict]) -> str:
    pairs = sorted((item["fetch_url"], item["digest"]) for item in pending)
    blob = "\n".join(f"{url}\t{digest}" for url, digest in pairs)
    return hashlib.sha256(blob.encode()).hexdigest()


def _pg_safe(value: str) -> str:
    return value.replace("\x00", "")


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


async def _bump_source(session: AsyncSession, source: KbSource, field: str) -> None:
    column = getattr(KbSource, field)
    await session.execute(
        update(KbSource).where(KbSource.id == source.id).values({field: column + 1})
    )
    await session.refresh(source, attribute_names=[field])


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


async def _fail_page(
    session: AsyncSession,
    source: KbSource,
    page: KbPage,
    job: KbPageJob,
    code: str,
    message: str | None = None,
) -> None:
    page.processing_status = "failed"
    page.failure_reason = code
    page.skip_reason = code
    job.state = "dead_letter"
    job.last_error_code = code
    job.last_error_message = _pg_safe(message or "")[:1000] or None
    job.finished_at = datetime.now(UTC)
    _record_job_event(job, job.stage, "dead_letter", error_code=code)
    await _bump_source(session, source, "pages_failed")
    await session.commit()


def _stage_error_code(stage: str) -> str:
    return {
        "fetch": "fetch",
        "extract": "extract",
        "llm_extract": "llm_extract",
        "embed": "embed",
        "persist": "persist",
    }.get(stage, "ingest")


def _record_job_event(
    job: KbPageJob,
    stage: str,
    state: str,
    *,
    error_code: str | None = None,
    renderer: str | None = None,
) -> None:
    from app.services.kb_progress import describe_progress_event

    events = list(job.events or [])
    events.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "stage": stage,
            "state": state,
            "error_code": error_code,
            "renderer": renderer or job.renderer,
            "http_status": job.http_status,
            "message": describe_progress_event(stage=stage, state=state, error_code=error_code),
        }
    )
    job.events = events[-50:]


async def _copy_live_chunks(
    session: AsyncSession, page: KbPage, live_id: UUID, snapshot_id: UUID
) -> tuple[int, int]:
    rows = list(
        (
            await session.scalars(
                select(KbChunk).where(KbChunk.page_id == page.id, KbChunk.snapshot_id == live_id)
            )
        ).all()
    )
    copied = 0
    token_total = 0
    for chunk in rows:
        session.add(
            KbChunk(
                page_id=page.id,
                site_id=chunk.site_id,
                snapshot_id=snapshot_id,
                ordinal=chunk.ordinal,
                kind=chunk.kind,
                heading=chunk.heading,
                canonical_question=chunk.canonical_question,
                answer_verbatim=chunk.answer_verbatim,
                aliases=list(chunk.aliases or []),
                topic=chunk.topic,
                approved=chunk.approved,
                review_status=chunk.review_status,
                reviewed_by=chunk.reviewed_by,
                reviewed_at=chunk.reviewed_at,
                review_note=chunk.review_note,
                content_hash=chunk.content_hash,
                risk_class=chunk.risk_class,
                answer_mode=chunk.answer_mode,
                topic_label=chunk.topic_label,
                requires_human=chunk.requires_human,
                legal_sensitive=chunk.legal_sensitive,
                display_locator=chunk.display_locator,
                body=chunk.body,
                context_prefix=chunk.context_prefix,
                embedding=chunk.embedding,
                enabled=chunk.enabled,
            )
        )
        copied += 1
        token_total += count_embed_tokens(chunk.body)
    if copied:
        await session.flush()
    return copied, token_total


async def _clean_units(
    session: AsyncSession,
    page: KbPage,
    digest: str,
    units: list[EvidenceUnit],
    llm_client,
    lock: asyncio.Lock | None = None,
    *,
    crawl_text: str | None = None,
    crawl_title: str = "",
    crawl_metadata: dict | None = None,
) -> list[EvidenceUnit]:
    if crawl_text is None:
        return apply_cleaner(units)
    version = f"{CONTENT_FINGERPRINT_VERSION}:{getattr(llm_client, 'model', 'local')}"
    gate = lock or asyncio.Lock()
    async with gate:
        cached = await session.scalar(
            select(KbPageLlmExtract).where(
                KbPageLlmExtract.page_id == page.id,
                KbPageLlmExtract.content_sha256 == digest,
                KbPageLlmExtract.prompt_version == version,
            )
        )
        if cached is not None:
            restored = _units_from_payload(cached.payload)
            if restored is not None:
                return restored
    structured = await llm_client.structure_page(page.url, crawl_title, crawl_text, crawl_metadata)
    payload = _units_payload(structured.units)
    async with gate:
        session.add(
            KbPageLlmExtract(
                page_id=page.id,
                content_sha256=digest,
                prompt_version=version,
                payload=payload,
                model=getattr(llm_client, "model", "local"),
                input_tokens=structured.input_tokens,
                output_tokens=structured.output_tokens,
                cache_read_tokens=structured.cache_read_tokens,
            )
        )
        await session.flush()
    return structured.units


def _units_payload(units: list[EvidenceUnit]) -> dict:
    return {
        "units": [
            {
                "kind": unit.kind,
                "heading": unit.heading,
                "canonical_question": unit.canonical_question,
                "answer_verbatim": unit.answer_verbatim,
                "aliases": list(unit.aliases),
                "topic": unit.topic,
                "display_locator": unit.display_locator,
                "structured_text": unit.structured_text,
                "enabled": unit.enabled,
                "review_note": unit.review_note,
            }
            for unit in units
        ]
    }


def _units_from_payload(payload: dict) -> list[EvidenceUnit] | None:
    if not isinstance(payload, dict):
        return None
    rows = payload.get("units")
    if not isinstance(rows, list):
        return None
    units: list[EvidenceUnit] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        answer = str(row.get("answer_verbatim") or "")
        heading = str(row.get("heading") or "")
        if not answer:
            continue
        kind = str(row.get("kind") or "section")
        if kind not in {"faq", "section", "table", "definition", "prose", "fact"}:
            kind = "section"
        aliases = row.get("aliases") or []
        units.append(
            EvidenceUnit(
                kind=kind,  # type: ignore[arg-type]
                heading=heading,
                canonical_question=str(row["canonical_question"])
                if row.get("canonical_question")
                else None,
                answer_verbatim=answer,
                body_for_search=f"{row.get('canonical_question') or heading}\n{row.get('structured_text') or answer}",
                display_locator=str(row["display_locator"]) if row.get("display_locator") else None,
                aliases=tuple(str(item) for item in aliases if isinstance(item, str)),
                topic=str(row["topic"]) if row.get("topic") else None,
                structured_text=str(row["structured_text"]) if row.get("structured_text") else None,
                enabled=bool(row.get("enabled", True)),
                review_note=str(row["review_note"]) if row.get("review_note") else None,
            )
        )
    return units


async def _persist_chunks(
    session: AsyncSession,
    source: KbSource,
    page: KbPage,
    snapshot_id: UUID,
    pieces: list[TextChunk],
    vectors: list[list[float]],
) -> None:
    live_rows = list(
        (
            await session.scalars(
                select(KbChunk)
                .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
                .where(KbSnapshot.source_id == source.id, KbSnapshot.state == "live")
            )
        ).all()
    )
    reviewed_by_hash = {chunk.content_hash: chunk for chunk in live_rows if chunk.content_hash}
    for ordinal, part in enumerate(pieces):
        _add_chunk_row(
            session,
            source,
            page,
            snapshot_id,
            ordinal,
            part,
            vectors[ordinal] if vectors else None,
            reviewed_by_hash,
        )
    await session.flush()


async def _prepare_chunks(
    units: list[EvidenceUnit], worker: Embedder
) -> tuple[list[TextChunk], list[list[float]], int]:
    settings = get_settings()
    pieces: list[TextChunk] = []
    for unit in units:
        pieces.extend(
            pack_chunks(
                unit,
                settings.chunk_target_chars,
                settings.chunk_overlap_chars,
            )
        )
    pieces = split_chunks_for_embed(pieces, settings.openai_embed_max_tokens)
    texts = [part.body for part in pieces]
    vectors = await worker.embed_documents(texts) if texts else []
    if texts and (len(vectors) != len(texts) or any(item is None for item in vectors)):
        raise RuntimeError("embed")
    return pieces, vectors, sum(count_embed_tokens(part.body) for part in pieces)


def _add_chunk_row(
    session: AsyncSession,
    source: KbSource,
    page: KbPage,
    snapshot_id: UUID,
    ordinal: int,
    part: TextChunk,
    vector: list[float] | None,
    reviewed_by_hash: dict[str, KbChunk],
) -> None:
    heading = _pg_safe(part.heading or "")
    canonical_question = _pg_safe(part.canonical_question or "") or None
    aliases = [_pg_safe(alias) for alias in part.aliases]
    answer_verbatim = _pg_safe(part.answer_verbatim or "")
    body = _pg_safe(part.body)
    content_hash = _chunk_content_hash(
        heading=heading,
        canonical_question=canonical_question,
        aliases=aliases,
        answer_verbatim=answer_verbatim,
        body=body,
    )
    prior = reviewed_by_hash.get(content_hash)
    session.add(
        KbChunk(
            page_id=page.id,
            site_id=source.site_id,
            snapshot_id=snapshot_id,
            ordinal=ordinal,
            kind=part.kind,
            heading=heading,
            canonical_question=canonical_question,
            answer_verbatim=answer_verbatim,
            aliases=aliases,
            topic=part.topic,
            display_locator=part.display_locator,
            body=body,
            context_prefix=part.context_prefix,
            embedding=vector,
            enabled=prior.enabled if prior is not None else part.enabled,
            review_note=prior.review_note if prior is not None else part.review_note,
            approved=True,
            review_status="approved",
            topic_label=(prior.topic_label if prior is not None else heading) or heading,
            content_hash=content_hash,
            risk_class=prior.risk_class if prior is not None else "general",
            answer_mode=prior.answer_mode if prior is not None else "paraphrase_allowed",
        )
    )


def _chunk_content_hash(
    *,
    heading: str,
    canonical_question: str | None,
    aliases: list[str],
    answer_verbatim: str,
    body: str,
) -> str:
    payload = json.dumps(
        {
            "aliases": aliases,
            "answer_verbatim": answer_verbatim,
            "body": body,
            "canonical_question": canonical_question,
            "heading": heading,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
