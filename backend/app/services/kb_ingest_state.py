"""Source counters and page-job state shared by ingest stages."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_page import KbPage
from app.models.kb_page_job import KbPageJob
from app.models.kb_source import KbSource
from app.settings import get_settings

CONTENT_FINGERPRINT_VERSION = "source-passages-v14"


def _content_fingerprint(raw_digest: str) -> str:
    return f"{CONTENT_FINGERPRINT_VERSION}:{get_settings().haiku_model}:{raw_digest}"


_STAGE_STATUS = dict.fromkeys(
    {"discovering", "processing", "validating", "promoting"}, "running"
) | {
    "failed": "failed",
    "ready": "ready",
}


def _sync_status(source: KbSource) -> None:
    source.status = _STAGE_STATUS.get(source.stage, source.status)


def _pg_safe(value: str) -> str:
    return value.replace("\x00", "")


async def _bump_source(session: AsyncSession, source: KbSource, field: str) -> None:
    column = getattr(KbSource, field)
    await session.execute(
        update(KbSource).where(KbSource.id == source.id).values({field: column + 1})
    )
    await session.refresh(source, attribute_names=[field])


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
    return stage if stage in {"fetch", "extract", "llm_extract", "embed", "persist"} else "ingest"


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
