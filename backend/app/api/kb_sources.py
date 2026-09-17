from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db import SessionDep
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_source import KbSource
from app.security.deps import CurrentAdmin, CurrentUser
from app.services.kb_source_admin import KbSourceService, general_tab_id
from app.services.site_admin import AdminError

router = APIRouter()


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["website", "text"] = "website"
    mode: str | None = None
    start_url: str | None = None
    seed_urls: list[str] = Field(default_factory=list)
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=40_000)

    @model_validator(mode="after")
    def validate_source_shape(self) -> "SourceIn":
        if self.kind == "website":
            if (
                self.mode is None
                or self.start_url is None
                or self.title is not None
                or self.body is not None
            ):
                raise ValueError("A website source requires mode and start_url")
        elif self.kind == "text":
            if (
                not (self.title or "").strip()
                or not (self.body or "").strip()
                or self.mode is not None
                or self.start_url is not None
                or self.seed_urls
            ):
                raise ValueError("A text source requires title and body")
        return self


class SourcePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=40_000)


class PagePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class ChunkPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class SourceOut(BaseModel):
    id: UUID
    site_id: UUID
    start_url: str
    mode: str
    source_kind: str
    display_name: str | None = None
    status: str
    stage: str = "idle"
    error_code: str | None
    page_count: int
    pages_discovered: int = 0
    pages_fetched: int = 0
    pages_extracted: int = 0
    pages_embedded: int = 0
    pages_failed: int = 0
    pages_skipped_unchanged: int = 0
    last_run_started_at: str | None = None
    last_run_finished_at: str | None = None
    enabled: bool
    snapshot_state: str | None = None
    snapshot_error_code: str | None = None
    validation_errors: list[str] = Field(default_factory=list)


class SourceListOut(BaseModel):
    items: list[SourceOut]


class SnapshotOut(BaseModel):
    id: UUID
    state: str
    created_at: str | None
    promoted_at: str | None
    token_estimate: int
    validation_errors: list[str]
    error_code: str | None


class SnapshotListOut(BaseModel):
    items: list[SnapshotOut]


class EvidenceUnitOut(BaseModel):
    kind: str
    canonical_question: str | None
    heading: str
    answer_verbatim: str
    display_locator: str | None


class DiffChangeOut(BaseModel):
    before: EvidenceUnitOut
    after: EvidenceUnitOut


class DiffOut(BaseModel):
    added: list[EvidenceUnitOut]
    changed: list[DiffChangeOut]
    removed: list[EvidenceUnitOut]


class PageOut(BaseModel):
    id: UUID
    source_id: UUID
    url: str
    title: str
    enabled: bool
    chunk_count: int
    processing_status: str = "pending"
    failure_reason: str | None = None
    last_success_at: str | None = None
    tab: str = "page"


class ChunkOut(BaseModel):
    id: UUID
    ordinal: int
    kind: str
    heading: str
    body: str
    enabled: bool
    origin_urls: list[str] = Field(default_factory=list)


class PageDetailOut(BaseModel):
    id: UUID
    source_id: UUID
    url: str
    title: str
    enabled: bool
    chunk_count: int
    skip_reason: str | None
    content_text: str
    chunks: list[ChunkOut]
    processing_status: str = "pending"
    failure_reason: str | None = None
    last_success_at: str | None = None
    tab: str = "page"


class ProgressEventOut(BaseModel):
    timestamp: str | None
    stage: str
    state: str
    page_url: str
    duration_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    message: str
    renderer: str | None = None
    http_status: int | None = None


class ProgressJobOut(BaseModel):
    page_url: str
    stage: str
    attempt: int
    started_at: str | None
    renderer: str | None = None
    message: str


class ProgressOut(BaseModel):
    source: SourceOut
    recent_events: list[ProgressEventOut]
    current_jobs: list[ProgressJobOut]


class PageListOut(BaseModel):
    items: list[PageOut]


def _http_error(exc: AdminError) -> HTTPException:
    if exc.code == "not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if exc.code == "invalid_origin":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid origin"
        )
    if exc.code == "too_large":
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Too large")
    if exc.code == "overlap":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This page already belongs to another knowledge source.",
        )
    if exc.code == "busy":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This source is already syncing.",
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid request"
    )


async def _source_out(session, source: KbSource) -> SourceOut:
    rows = await KbSourceService(session).list_snapshots(source.id)
    latest = rows[0] if rows else None
    live = next((row for row in rows if row.state == "live"), None)
    serving = live or latest
    failed_run = latest if latest is not None and latest.state == "failed" else None
    return SourceOut(
        id=source.id,
        site_id=source.site_id,
        start_url="" if source.source_kind == "text" else source.start_url,
        mode=source.mode,
        source_kind=source.source_kind,
        display_name=source.display_name,
        status=source.status,
        stage=source.stage or "idle",
        error_code=source.error_code,
        page_count=source.page_count,
        pages_discovered=source.pages_discovered,
        pages_fetched=source.pages_fetched,
        pages_extracted=source.pages_extracted,
        pages_embedded=source.pages_embedded,
        pages_failed=source.pages_failed,
        pages_skipped_unchanged=source.pages_skipped_unchanged,
        last_run_started_at=_iso(source.last_run_started_at),
        last_run_finished_at=_iso(source.last_run_finished_at),
        enabled=source.enabled,
        snapshot_state=serving.state if serving is not None else None,
        snapshot_error_code=(
            failed_run.error_code
            if failed_run is not None
            else (serving.error_code if serving is not None else None)
        ),
        validation_errors=list((failed_run or serving).validation_errors or [])
        if (failed_run or serving) is not None
        else [],
    )


def _page_tab(page: KbPage) -> str:
    return "general" if page.id == general_tab_id(page.source_id) else "page"


def _chunk_out(chunk: KbChunk) -> ChunkOut:
    return ChunkOut(
        id=chunk.id,
        ordinal=chunk.ordinal,
        kind=chunk.kind,
        heading=chunk.heading,
        body=chunk.body,
        enabled=chunk.enabled,
        origin_urls=list(chunk.origin_urls or []),
    )


def _page_out(page: KbPage, chunk_count: int) -> PageOut:
    return PageOut(
        id=page.id,
        source_id=page.source_id,
        url=page.public_url,
        title=page.title,
        enabled=page.enabled,
        chunk_count=chunk_count,
        processing_status=page.processing_status,
        failure_reason=page.failure_reason,
        last_success_at=_iso(page.last_success_at),
        tab=_page_tab(page),
    )


def _page_detail_out(page: KbPage, chunks: list[KbChunk]) -> PageDetailOut:
    return PageDetailOut(
        id=page.id,
        source_id=page.source_id,
        url=page.public_url,
        title=page.title,
        enabled=page.enabled,
        chunk_count=len(chunks),
        skip_reason=page.skip_reason,
        content_text=page.content_text,
        chunks=[_chunk_out(chunk) for chunk in chunks],
        processing_status=page.processing_status,
        failure_reason=page.failure_reason,
        last_success_at=_iso(page.last_success_at),
        tab=_page_tab(page),
    )


@router.get("/api/sites/{site_id}/kb-sources", response_model=SourceListOut)
async def list_sources(site_id: UUID, session: SessionDep, _staff: CurrentUser) -> SourceListOut:
    try:
        rows = await KbSourceService(session).list_sources(site_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    items = [await _source_out(session, row) for row in rows]
    return SourceListOut(items=items)


@router.post(
    "/api/sites/{site_id}/kb-sources",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    site_id: UUID, payload: SourceIn, session: SessionDep, admin: CurrentAdmin
) -> SourceOut:
    try:
        service = KbSourceService(session)
        if payload.kind == "text":
            source = await service.create_text_source(
                site_id,
                admin,
                title=payload.title or "",
                body=payload.body or "",
            )
        else:
            source = await service.create_source(
                site_id,
                admin,
                mode=payload.mode or "",
                start_url=payload.start_url or "",
                seed_urls=payload.seed_urls,
            )
    except AdminError as exc:
        raise _http_error(exc) from exc
    return await _source_out(session, source)


@router.patch("/api/kb-sources/{source_id}", response_model=SourceOut)
async def patch_source(
    source_id: UUID, payload: SourcePatchIn, session: SessionDep, admin: CurrentAdmin
) -> SourceOut:
    try:
        source = await KbSourceService(session).patch_source(
            source_id,
            enabled=payload.enabled,
            title=payload.title,
            body=payload.body,
        )
    except AdminError as exc:
        raise _http_error(exc) from exc
    return await _source_out(session, source)


@router.patch("/api/kb-chunks/{chunk_id}", response_model=ChunkOut)
async def patch_chunk(
    chunk_id: UUID, payload: ChunkPatchIn, session: SessionDep, _admin: CurrentAdmin
) -> ChunkOut:
    try:
        chunk = await KbSourceService(session).patch_chunk(chunk_id, enabled=payload.enabled)
    except AdminError as exc:
        if exc.code == "stale":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This retrieved answer was replaced during sync.",
            ) from exc
        raise _http_error(exc) from exc
    return _chunk_out(chunk)


@router.post("/api/kb-sources/{source_id}/sync", response_model=SourceOut)
async def sync_source(source_id: UUID, session: SessionDep, admin: CurrentAdmin) -> SourceOut:
    try:
        source = await KbSourceService(session).sync_source(source_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    return await _source_out(session, source)


@router.post("/api/kb-pages/{page_id}/retry", response_model=SourceOut)
async def retry_page(page_id: UUID, session: SessionDep, admin: CurrentAdmin) -> SourceOut:
    try:
        source = await KbSourceService(session).retry_page(page_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    return await _source_out(session, source)


@router.delete("/api/kb-sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: UUID, session: SessionDep, admin: CurrentAdmin) -> None:
    try:
        await KbSourceService(session).delete_source(source_id)
    except AdminError as exc:
        raise _http_error(exc) from exc


@router.get("/api/kb-sources/{source_id}/pages", response_model=PageListOut)
async def list_pages(source_id: UUID, session: SessionDep, _staff: CurrentUser) -> PageListOut:
    try:
        rows = await KbSourceService(session).list_pages(source_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    return PageListOut(items=[_page_out(page, chunk_count) for page, chunk_count in rows])


@router.get("/api/kb-sources/{source_id}/progress", response_model=ProgressOut)
async def source_progress(source_id: UUID, session: SessionDep, _staff: CurrentUser) -> ProgressOut:
    source = await session.get(KbSource, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    from sqlalchemy import select

    from app.services.kb_progress import describe_progress_event

    result = await session.execute(
        select(KbPageJob, KbPage)
        .join(KbPage, KbPage.id == KbPageJob.page_id)
        .where(KbPageJob.source_id == source_id)
        .order_by(KbPageJob.finished_at.desc().nullslast(), KbPageJob.created_at.desc())
    )
    rows = list(result.all())
    recent: list[ProgressEventOut] = []
    current: list[ProgressJobOut] = []
    for job, page in rows:
        page_locator = page.public_url or page.title
        duration = None
        if job.started_at is not None and job.finished_at is not None:
            duration = round((job.finished_at - job.started_at).total_seconds() * 1000)
        for event in reversed(job.events or []):
            if len(recent) >= 20:
                break
            stage = str(event.get("stage") or job.stage)
            state = str(event.get("state") or job.state)
            error_code = event.get("error_code")
            recent.append(
                ProgressEventOut(
                    timestamp=event.get("timestamp"),
                    stage=stage,
                    state=state,
                    page_url=page_locator,
                    duration_ms=(
                        duration if state in {"done", "dead_letter", "unchanged"} else None
                    ),
                    error_code=error_code,
                    error_message=(job.last_error_message if error_code else None),
                    message=str(
                        event.get("message")
                        or describe_progress_event(stage=stage, state=state, error_code=error_code)
                    ),
                    renderer=event.get("renderer") or job.renderer,
                    http_status=event.get("http_status") or job.http_status,
                )
            )
        if not job.events and job.finished_at is not None and len(recent) < 20:
            recent.append(
                ProgressEventOut(
                    timestamp=_iso(job.finished_at),
                    stage=job.stage,
                    state=job.state,
                    page_url=page_locator,
                    duration_ms=duration,
                    error_code=job.last_error_code,
                    error_message=job.last_error_message,
                    message=describe_progress_event(
                        stage=job.stage, state=job.state, error_code=job.last_error_code
                    ),
                    renderer=job.renderer,
                    http_status=job.http_status,
                )
            )
        if job.state == "running":
            current.append(
                ProgressJobOut(
                    page_url=page_locator,
                    stage=job.stage,
                    attempt=job.attempts,
                    started_at=_iso(job.started_at),
                    renderer=job.renderer,
                    message=describe_progress_event(
                        stage=job.stage, state=job.state, error_code=job.last_error_code
                    ),
                )
            )
    return ProgressOut(
        source=await _source_out(session, source),
        recent_events=recent,
        current_jobs=current,
    )


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _unit_out(item: dict) -> EvidenceUnitOut:
    return EvidenceUnitOut(
        kind=item["kind"],
        canonical_question=item["canonical_question"],
        heading=item["heading"],
        answer_verbatim=item["answer_verbatim"],
        display_locator=item["display_locator"],
    )


@router.get("/api/kb-sources/{source_id}/snapshots", response_model=SnapshotListOut)
async def list_snapshots(
    source_id: UUID, session: SessionDep, _staff: CurrentUser
) -> SnapshotListOut:
    try:
        rows = await KbSourceService(session).list_snapshots(source_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    return SnapshotListOut(
        items=[
            SnapshotOut(
                id=row.id,
                state=row.state,
                created_at=_iso(row.created_at),
                promoted_at=_iso(row.promoted_at),
                token_estimate=row.token_estimate,
                validation_errors=list(row.validation_errors or []),
                error_code=row.error_code,
            )
            for row in rows
        ]
    )


@router.get("/api/kb-sources/{source_id}/diff", response_model=DiffOut)
async def snapshot_diff(
    source_id: UUID,
    session: SessionDep,
    _staff: CurrentUser,
    from_id: Annotated[UUID | None, Query(alias="from")] = None,
    to_id: Annotated[UUID | None, Query(alias="to")] = None,
) -> DiffOut:
    try:
        payload = await KbSourceService(session).diff_snapshots(source_id, from_id, to_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    return DiffOut(
        added=[_unit_out(item) for item in payload["added"]],
        changed=[
            DiffChangeOut(before=_unit_out(item["before"]), after=_unit_out(item["after"]))
            for item in payload["changed"]
        ],
        removed=[_unit_out(item) for item in payload["removed"]],
    )


@router.post("/api/kb-sources/{source_id}/rollback", response_model=SnapshotOut)
async def rollback_source(source_id: UUID, session: SessionDep, admin: CurrentAdmin) -> SnapshotOut:
    try:
        row = await KbSourceService(session).rollback_source(source_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    return SnapshotOut(
        id=row.id,
        state=row.state,
        created_at=_iso(row.created_at),
        promoted_at=_iso(row.promoted_at),
        token_estimate=row.token_estimate,
        validation_errors=list(row.validation_errors or []),
        error_code=row.error_code,
    )


@router.get("/api/kb-pages/{page_id}", response_model=PageDetailOut)
async def get_page(page_id: UUID, session: SessionDep, _staff: CurrentUser) -> PageDetailOut:
    try:
        page, chunks = await KbSourceService(session).get_page(page_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    return _page_detail_out(page, chunks)


@router.patch("/api/kb-pages/{page_id}", response_model=PageOut)
async def patch_page(
    page_id: UUID, payload: PagePatchIn, session: SessionDep, admin: CurrentAdmin
) -> PageOut:
    service = KbSourceService(session)
    try:
        page = await service.patch_page(page_id, enabled=payload.enabled)
        _, chunks = await service.get_page(page_id)
    except AdminError as exc:
        raise _http_error(exc) from exc
    return _page_out(page, len(chunks))
