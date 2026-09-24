import asyncio
from datetime import timedelta

import structlog

from app.chat.connection_manager import connection_manager
from app.db import session_maker
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.handoff_repo import HandoffRepository
from app.services import handoff_summary
from app.services.conversation_service import ConversationService
from app.settings import get_settings

log = structlog.get_logger("durable_work")
_task: asyncio.Task | None = None


async def _claim_bot() -> tuple | None:
    settings = get_settings()
    async with session_maker()() as session:
        return await ConversationRepository(session).claim_recoverable_generation(
            recovery_grace=timedelta(seconds=settings.bot_generation_recovery_grace_seconds),
            lease=timedelta(seconds=settings.bot_generation_lease_seconds),
        )


async def _run_bot(claim: tuple) -> None:
    conversation_id, generation_id = claim
    async with session_maker()() as session:
        result = await ConversationService(session).run_bot_turn(
            conversation_id, generation_id, already_claimed=True
        )
    if result is not None:
        await connection_manager.after_commit(
            result.conversation,
            result.site_key,
            result.message.id if result.message is not None else None,
        )


async def _claim_summary():
    settings = get_settings()
    async with session_maker()() as session:
        return await HandoffRepository(session).claim_next_summary(
            lease=timedelta(seconds=max(settings.haiku_timeout * 3, 30))
        )


async def _run_summary(row) -> None:
    try:
        async with session_maker()() as session:
            await handoff_summary.generate(
                session,
                handoff_id=row.id,
                conversation_id=row.conversation_id,
                original_question=row.original_question,
                escalation_reason=row.escalation_reason,
            )
            await session.commit()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        settings = get_settings()
        async with session_maker()() as session:
            await HandoffRepository(session).retry_or_fail_summary(
                row.id,
                error=type(exc).__name__,
                max_attempts=settings.handoff_summary_max_attempts,
                retry_delay=timedelta(seconds=min(2 ** max(row.summary_attempts, 1), 60)),
            )
            await session.commit()
        log.info("handoff_summary_job_failed", error_class=type(exc).__name__)


async def durable_work_loop() -> None:
    while True:
        try:
            bot_claim = await _claim_bot()
            if bot_claim is not None:
                await _run_bot(bot_claim)
                continue
            summary = await _claim_summary()
            if summary is not None:
                await _run_summary(summary)
                continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.info("durable_work_failed", error_class=type(exc).__name__)
        await asyncio.sleep(get_settings().background_job_poll_seconds)


async def start_durable_work() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(durable_work_loop())


async def stop_durable_work() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
