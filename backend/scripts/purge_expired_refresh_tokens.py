import argparse
import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, func, select

from app.db import session_maker
from app.logging import configure_logging
from app.models.refresh_token import RefreshToken

log = structlog.get_logger("purge_refresh_tokens")
BATCH = 500


async def purge_expired_refresh_tokens(
    now: datetime | None = None,
    dry_run: bool = False,
    batch_size: int = BATCH,
) -> int:
    """Delete only naturally expired tokens.

    Rotated (replaced_at) and revoked rows are retained until expires_at so
    reuse detection can still revoke the active family.
    """
    moment = now or datetime.now(UTC)
    stale = RefreshToken.expires_at <= moment
    async with session_maker()() as session:
        total = int(
            await session.scalar(select(func.count()).select_from(RefreshToken).where(stale)) or 0
        )
        if dry_run:
            log.info("purge_refresh_tokens_dry_run", rows=total)
            return total
        deleted = 0
        while True:
            ids = list(
                await session.scalars(select(RefreshToken.id).where(stale).limit(batch_size))
            )
            if not ids:
                break
            await session.execute(delete(RefreshToken).where(RefreshToken.id.in_(ids)))
            await session.commit()
            deleted += len(ids)
            log.info("purge_refresh_tokens_batch", rows=len(ids))
        log.info("purge_refresh_tokens_complete", rows=deleted)
        return deleted


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Delete expired refresh tokens.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(purge_expired_refresh_tokens(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
