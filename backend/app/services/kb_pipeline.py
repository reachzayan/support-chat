from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
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
from app.services.kb_alias import generate_aliases
from app.services.kb_backoff import classify_error, next_run_at, should_dead_letter
from app.services.kb_chunk import pack_chunks, split_chunks_for_embed
from app.services.kb_crawl import (
    FetchError,
    parse_sitemap_locs,
    sitemap_urls_from_robots,
)
from app.services.kb_embedder import Embedder, FakeEmbedder, OversizeChunkError, count_embed_tokens
from app.services.kb_extract import extract_html
from app.services.kb_extract.text import visible_copy
from app.services.kb_extract.types import EvidenceUnit
from app.services.kb_fetcher import fetch_page
from app.services.kb_host_limiter import HostLimiter
from app.services.kb_llm_extract import (
    PROMPT_VERSION_DEFAULT,
    evidence_from_extraction,
    needs_llm_extraction,
)
from app.services.kb_snapshot import begin_snapshot, fail, validate_snapshot
from app.settings import get_settings

log = structlog.get_logger("kb_pipeline")


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
    from app.services.kb_crawl import fetch_html as http_fetch
    from app.services.kb_ingest import allowed_hosts_for

    source = await session.get(KbSource, source_id)
    if source is None:
        return
    site = await session.get(Site, source.site_id)
    if site is None:
        return
    now = datetime.now(UTC)
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
    hosts = allowed_hosts_for(site, source.start_url)
    robots: dict[str, str | None] = {}
    seen: set[str] = set()
    extra_urls: list[str] = []
    pending: list[dict] = []
    jobs = KbPageJobRepository(session)
    discover_fetch = fetch if fetch is not None else http_fetch
    limiter = HostLimiter(get_settings().kb_ingest_host_delay_ms)
    db_lock = asyncio.Lock()
    page_sem = asyncio.Semaphore(max(1, get_settings().kb_ingest_page_concurrency))

    planned = _planned_urls(source, site, hosts, discover_fetch, robots)
    source.stage = "processing"
    _sync_status(source)
    await session.commit()

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
                )
            except Exception as exc:
                log.info(
                    "kb_stage",
                    source_id=str(source.id),
                    stage="process",
                    state_to="failed",
                    error_code=type(exc).__name__,
                )
                return
            if item:
                pending.append(item)

    await _run_page_group(handle, planned)
    if source.mode == "prefix":
        remaining = source.max_pages - len(seen)
        await _run_page_group(handle, extra_urls[: max(remaining, 0)])
    source.pages_discovered = len(seen)
    await _finish_ingest(session, source, snapshot_id, pending)


async def _fail_empty(session: AsyncSession, source: KbSource, snapshot_id: UUID) -> None:
    await fail(session, snapshot_id, "empty")
    source.stage = "failed"
    source.status = "failed"
    source.error_code = "empty"
    source.last_error_code = "empty"
    source.last_run_finished_at = datetime.now(UTC)
    await session.commit()


async def _mark_unchanged(
    session: AsyncSession, source: KbSource, snapshot_id: UUID, pending: list[dict]
) -> None:
    await fail(session, snapshot_id, "unchanged")
    source.stage = "ready"
    source.status = "ready"
    source.error_code = None
    source.page_count = len(pending)
    source.last_run_finished_at = datetime.now(UTC)
    await session.commit()


async def _finish_ingest(
    session: AsyncSession, source: KbSource, snapshot_id: UUID, pending: list[dict]
) -> None:
    if not pending and source.pages_embedded == 0 and source.pages_skipped_unchanged == 0:
        await _fail_empty(session, source, snapshot_id)
        return
    content_hash = _content_hash(pending)
    baseline = await session.scalar(
        select(KbSnapshot)
        .where(
            KbSnapshot.source_id == source.id,
            KbSnapshot.state == "live",
        )
        .order_by(KbSnapshot.created_at.desc())
    )
    if baseline is not None and baseline.content_hash == content_hash and source.pages_failed == 0:
        await _mark_unchanged(session, source, snapshot_id, pending)
        return
    live = await session.scalar(
        select(KbSnapshot).where(KbSnapshot.source_id == source.id, KbSnapshot.state == "live")
    )
    if live is not None:
        for item in pending:
            if not item.get("copy_from_live"):
                continue
            page = await session.get(KbPage, item["page_id"])
            if page is not None:
                copied = await _copy_live_chunks(session, page, live.id, snapshot_id)
                if copied:
                    source.pages_embedded += 1
    snapshot = await session.get(KbSnapshot, snapshot_id)
    if snapshot is not None:
        snapshot.content_hash = content_hash
        snapshot.token_estimate = sum(item.get("token_estimate", 0) for item in pending)
    source.stage = "validating"
    _sync_status(source)
    result = await validate_snapshot(session, snapshot_id)
    if result.failed_rules:
        source.stage = "failed"
        source.status = "failed"
        source.last_run_finished_at = datetime.now(UTC)
        await session.commit()
        return
    # Site owners explicitly add the source, so a validated snapshot becomes
    # the live source immediately.  There is no separate human-review gate.
    from app.services.kb_snapshot import promote

    await promote(session, snapshot_id)
    source.stage = "ready"
    source.status = "ready"
    source.error_code = None
    source.page_count = source.pages_embedded or len(pending)
    source.last_run_finished_at = datetime.now(UTC)
    await session.commit()


async def _run_page_group(handle, urls: list[str]) -> None:
    if not urls:
        return
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            tg.create_task(handle(url))


def _planned_urls(source: KbSource, site: Site, hosts: set[str], fetch, robots) -> list[str]:
    from app.services.kb_ingest import _plan_urls

    if source.mode == "prefix":
        sitemap_urls = _sitemap_seed_urls(source, site, hosts, fetch, robots)
        if sitemap_urls:
            return sitemap_urls[: source.max_pages]
    return _plan_urls(source)[: source.max_pages]


def _sitemap_seed_urls(source: KbSource, site: Site, hosts: set[str], fetch, robots) -> list[str]:
    from app.services.kb_ingest import _robots_body

    host = urlparse(source.start_url).hostname
    candidates: list[str] = []
    robots_body = _robots_body(source.start_url, hosts, fetch, robots) or ""
    candidates.extend(sitemap_urls_from_robots(robots_body))
    if host:
        candidates.append(f"https://{host.casefold()}/sitemap.xml")
        candidates.append(f"https://{host.casefold()}/sitemap_index.xml")
    locs = _expand_sitemap_locs(candidates, hosts, fetch)
    return _filter_sitemap_urls(locs, source, site)


def _expand_sitemap_locs(candidates: list[str], hosts: set[str], fetch) -> list[str]:
    from app.services.kb_ingest import _try_fetch

    locs: list[str] = []
    nested: list[str] = []
    seen: set[str] = set()
    for sitemap_url in candidates:
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        body = _try_fetch(sitemap_url, hosts, fetch)
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
        body = _try_fetch(sitemap_url, hosts, fetch)
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
) -> dict | None:
    from app.services.kb_crawl import fetch_html as http_fetch
    from app.services.kb_ingest import (
        CanonicalError,
        _robots_body,
        _url_allowed_by_source_rules,
        canonical_fetch_url,
        host_allowed,
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
        robots_body = _robots_body(
            fetch_url, hosts, fetch if fetch is not None else http_fetch, robots
        )
        if robots_body is not None and not _robots_ok(fetch_url, robots_body):
            return None

        page = await _ensure_page(session, source, fetch_url)
        job = await jobs.upsert(source_id=source.id, page_id=page.id, snapshot_id=snapshot_id)
        job.state = "running"
        job.stage = "fetch"
        job.started_at = started
        page.processing_status = "fetching"
        await session.commit()

    html, digest, markdown = await _fetch_with_retry(
        session, source, page, job, fetch_url, hosts, fetch, limiter, lock
    )
    return await _after_fetch(
        session,
        source,
        url,
        fetch_url,
        html,
        digest,
        markdown,
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
    html: str | None,
    digest: str,
    markdown: str,
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
    async with lock:
        if html is None:
            _log_fetch_failure(source, page, snapshot_id, job, started)
            return None
        await _bump_source(session, source, "pages_fetched")
        previous_hash = page.content_sha256
        page.raw_html = html
        page.markdown = (markdown or "").strip() or visible_copy(html)
        page.http_status = 200
        page.content_sha256 = digest
        page.processing_status = "fetched"
        job.stage = "extract"
        if source.mode == "prefix":
            _collect_prefix_links(html, fetch_url, source, extra_urls, seen)
        baseline = await session.scalar(
            select(KbSnapshot)
            .where(
                KbSnapshot.source_id == source.id,
                KbSnapshot.state == "live",
            )
            .order_by(KbSnapshot.created_at.desc())
        )
        if baseline is not None and previous_hash and previous_hash == digest:
            return await _mark_page_unchanged(session, source, page, job, fetch_url, digest)
        page.processing_status = "extracting"
        await session.commit()
        units = extract_html(html, url=url)
        if needs_llm_extraction(units):
            page.processing_status = "llm_extracting"
            job.stage = "llm_extract"
            await session.commit()
    extra: list[EvidenceUnit] = []
    if needs_llm_extraction(units):
        extra = await _llm_units(session, page, digest, markdown or html, llm_client, lock)
    return await _persist_extracted(
        session,
        source,
        url,
        fetch_url,
        digest,
        snapshot_id,
        worker,
        page,
        job,
        units + extra,
        lock,
        started,
    )


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
    html: str, fetch_url: str, source: KbSource, extra_urls: list[str], seen: set[str]
) -> None:
    from app.services.kb_ingest import _links_from, _same_prefix, _url_allowed_by_source_rules

    for link in _links_from(html, fetch_url):
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
    digest: str,
) -> dict:
    page.processing_status = "unchanged"
    page.last_success_at = datetime.now(UTC)
    job.state = "unchanged"
    job.stage = "persist"
    job.finished_at = datetime.now(UTC)
    await _bump_source(session, source, "pages_skipped_unchanged")
    await session.commit()
    return {
        "fetch_url": fetch_url,
        "digest": digest,
        "token_estimate": 0,
        "copy_from_live": True,
        "page_id": page.id,
    }


async def _persist_extracted(
    session: AsyncSession,
    source: KbSource,
    url: str,
    fetch_url: str,
    digest: str,
    snapshot_id: UUID,
    worker: Embedder,
    page: KbPage,
    job: KbPageJob,
    units: list[EvidenceUnit],
    lock: asyncio.Lock,
    started: datetime,
) -> dict | None:
    from app.services.kb_ingest import display_locator

    async with lock:
        if not units:
            page.processing_status = "failed"
            page.skip_reason = "empty"
            page.failure_reason = "empty"
            page.enabled = False
            job.state = "done"
            job.last_error_code = "empty"
            job.finished_at = datetime.now(UTC)
            await _bump_source(session, source, "pages_failed")
            await session.commit()
            return None
        await _bump_source(session, source, "pages_extracted")
        page.processing_status = "embedding"
        job.stage = "embed"
        page.title = _pg_safe(units[0].heading or "Untitled")
        page.content_text = _pg_safe("\n\n".join(unit.answer_verbatim for unit in units))
        page.display_locator = display_locator(url) or units[0].display_locator
        page.enabled = True
        page.skip_reason = None
        await session.commit()
        try:
            token_estimate = await _persist_chunks(
                session, source, page, snapshot_id, units, worker
            )
        except OversizeChunkError:
            await _fail_page(session, source, page, job, "oversize")
            return None
        except Exception:
            await _fail_page(session, source, page, job, "embed")
            return None
        page.processing_status = "ready"
        page.last_success_at = datetime.now(UTC)
        job.stage = "persist"
        job.state = "done"
        job.finished_at = datetime.now(UTC)
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
        }


async def _ensure_page(session: AsyncSession, source: KbSource, url: str) -> KbPage:
    pages = KbPageRepository(session)
    page = await pages.get_for_source_url(source.id, url)
    if page is not None:
        page.processing_status = "pending"
        page.failure_reason = None
        return page
    page = KbPage(
        source_id=source.id,
        site_id=source.site_id,
        url=url,
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
) -> tuple[str | None, str, str]:
    settings = get_settings()
    last_code = "http"
    max_attempts = job.max_attempts
    for attempt in range(1, max_attempts + 1):
        await limiter.wait_url(url)
        try:
            result = await fetch_page(url, hosts, fetch=fetch)
            async with lock:
                job.attempts = attempt
            return result.html, result.content_sha256, result.markdown
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
                    return None, "", ""
                job.state = "transient_failed"
                await session.commit()
            if settings.kb_ingest_retry_sleep > 0:
                await asyncio.sleep(settings.kb_ingest_retry_sleep)
    async with lock:
        await _fail_page(session, source, page, job, last_code)
    return None, "", ""


async def _fail_page(
    session: AsyncSession, source: KbSource, page: KbPage, job: KbPageJob, code: str
) -> None:
    page.processing_status = "failed"
    page.failure_reason = code
    page.skip_reason = code
    job.state = "dead_letter"
    job.last_error_code = code
    job.finished_at = datetime.now(UTC)
    await _bump_source(session, source, "pages_failed")
    await session.commit()


async def _copy_live_chunks(
    session: AsyncSession, page: KbPage, live_id: UUID, snapshot_id: UUID
) -> int:
    rows = list(
        (
            await session.scalars(
                select(KbChunk).where(KbChunk.page_id == page.id, KbChunk.snapshot_id == live_id)
            )
        ).all()
    )
    copied = 0
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
    if copied:
        await session.flush()
    return copied


async def _llm_units(
    session: AsyncSession,
    page: KbPage,
    digest: str,
    text: str,
    llm_client,
    lock: asyncio.Lock | None = None,
) -> list[EvidenceUnit]:
    settings = get_settings()
    version = settings.kb_llm_extract_prompt_version or PROMPT_VERSION_DEFAULT
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
            return evidence_from_extraction(cached.payload, text)
        if llm_client is None:
            return []
    payload = await llm_client.extract(text)
    async with gate:
        session.add(
            KbPageLlmExtract(
                page_id=page.id,
                content_sha256=digest,
                prompt_version=version,
                payload=payload,
                model=settings.haiku_model,
            )
        )
        await session.flush()
    return evidence_from_extraction(payload, text)


async def _persist_chunks(
    session: AsyncSession,
    source: KbSource,
    page: KbPage,
    snapshot_id: UUID,
    units: list[EvidenceUnit],
    worker: Embedder,
) -> int:
    settings = get_settings()
    pieces = []
    for unit in units:
        aliases = await generate_aliases(unit)
        pieces.extend(
            pack_chunks(
                replace(unit, aliases=aliases or unit.aliases),
                settings.chunk_target_chars,
                settings.chunk_overlap_chars,
            )
        )
    pieces = split_chunks_for_embed(pieces, settings.openai_embed_max_tokens)
    texts = [part.body for part in pieces]
    vectors = await worker.embed_documents(texts) if texts else []
    if texts and (len(vectors) != len(texts) or any(item is None for item in vectors)):
        raise RuntimeError("embed")
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
    token_total = 0
    for ordinal, part in enumerate(pieces):
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
        # Website content is trusted as knowledge once the site owner adds it.
        # Prompt-injection markers are still treated as document text by the
        # responder; they never become instructions.
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
                embedding=vectors[ordinal] if vectors else None,
                enabled=True,
                approved=True,
                review_status="approved",
                topic_label=(prior.topic_label if prior is not None else heading) or heading,
                content_hash=content_hash,
                risk_class=prior.risk_class if prior is not None else "general",
                answer_mode=prior.answer_mode if prior is not None else "paraphrase_allowed",
            )
        )
        token_total += count_embed_tokens(part.body)
    await session.flush()
    return token_total


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
