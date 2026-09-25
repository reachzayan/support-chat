import argparse
import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import delete, func, select

from app.db import session_maker
from app.logging import configure_logging
from app.models.app_log import AppLog
from app.repositories.app_log_repo import DEFAULT_RETENTION_DAYS

log = structlog.get_logger("purge_logs")
BATCH = 500


async def purge_expired_logs(
    now: datetime | None = None,
    dry_run: bool = False,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    batch_size: int = BATCH,
) -> int:
    if retention_days < 1:
        raise ValueError("retention_days must be a positive integer")
    moment = now or datetime.now(UTC)
    cutoff = moment - timedelta(days=retention_days)
    async with session_maker()() as session:
        total = int(
            await session.scalar(
                select(func.count()).select_from(AppLog).where(AppLog.created_at < cutoff)
            )
            or 0
        )
        if dry_run:
            log.info("purge_logs_dry_run", rows=total, cutoff=cutoff.isoformat())
            return total
        deleted = 0
        while True:
            ids = list(
                await session.scalars(
                    select(AppLog.id).where(AppLog.created_at < cutoff).limit(batch_size)
                )
            )
            if not ids:
                break
            await session.execute(delete(AppLog).where(AppLog.id.in_(ids)))
            await session.commit()
            deleted += len(ids)
            log.info("purge_logs_batch", rows=len(ids))
        log.info("purge_logs_complete", rows=deleted)
        return deleted


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Delete application logs older than retention.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    args = parser.parse_args()
    asyncio.run(purge_expired_logs(dry_run=args.dry_run, retention_days=args.retention_days))


if __name__ == "__main__":
    main()
