import asyncio
from datetime import timedelta

import structlog

from app.db import session_maker
from app.repositories.visitor_repo import VisitorRepository
from app.services.ip_geolocation import lookup_location
from app.settings import get_settings

log = structlog.get_logger("location_enrichment")
_task: asyncio.Task | None = None


async def location_enrichment_loop() -> None:
    while True:
        settings = get_settings()
        if not settings.ip_geolocation_provider_url:
            await asyncio.sleep(60)
            continue
        try:
            async with session_maker()() as session:
                claim = await VisitorRepository(session).claim_location_lookup(
                    retry_after=timedelta(hours=settings.ip_geolocation_retry_hours)
                )
            if claim is None:
                await asyncio.sleep(settings.background_job_poll_seconds)
                continue
            visitor_id, address = claim
            location = await lookup_location(
                str(address), provider_url=settings.ip_geolocation_provider_url
            )
            if location:
                async with session_maker()() as session:
                    visitor = await VisitorRepository(session).lock_by_id(visitor_id)
                    if visitor is not None and visitor.ip == address:
                        visitor.location = location
                    await session.commit()
            # FreeIPAPI allows 10 lookups per 10 seconds (60 per minute).
            await asyncio.sleep(max(1.1, settings.background_job_poll_seconds))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.info("location_enrichment_failed", error_class=type(exc).__name__)
            await asyncio.sleep(settings.background_job_poll_seconds)


async def start_location_enrichment() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(location_enrichment_loop())


async def stop_location_enrichment() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
