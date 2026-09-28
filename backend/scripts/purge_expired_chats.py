import argparse
import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import delete, exists, func, select

from app.db import session_maker
from app.logging import configure_logging
from app.models.conversation import Conversation
from app.models.visitor import Visitor
from app.settings import get_settings

log = structlog.get_logger("purge")
BATCH = 100


async def purge_expired(
    now: datetime | None = None,
    dry_run: bool = False,
    batch_size: int = BATCH,
) -> dict[str, int]:
    settings = get_settings()
    if settings.chat_retention_days < 1:
        raise ValueError("CHAT_RETENTION_DAYS must be a positive integer")
    moment = now or datetime.now(UTC)
    cutoff = moment - timedelta(days=settings.chat_retention_days)
    async with session_maker()() as session:
        expired = Conversation.last_message_at < cutoff
        conversation_count = int(
            await session.scalar(select(func.count()).select_from(Conversation).where(expired)) or 0
        )
        has_expired = exists(
            select(Conversation.id).where(
                Conversation.visitor_id == Visitor.id,
                Conversation.last_message_at < cutoff,
            )
        )
        has_kept = exists(
            select(Conversation.id).where(
                Conversation.visitor_id == Visitor.id,
                Conversation.last_message_at >= cutoff,
            )
        )
        visitor_count = int(
            await session.scalar(
                select(func.count()).select_from(Visitor).where(has_expired, ~has_kept)
            )
            or 0
        )
        counts = {"conversations": conversation_count, "visitors": visitor_count}
        if dry_run:
            log.info("purge_dry_run", conversations=conversation_count, visitors=visitor_count)
            return counts
        deleted_conversations = 0
        while True:
            ids = list(
                await session.scalars(select(Conversation.id).where(expired).limit(batch_size))
            )
            if not ids:
                break
            await session.execute(delete(Conversation).where(Conversation.id.in_(ids)))
            await session.commit()
            deleted_conversations += len(ids)
            log.info("purge_batch", conversations=len(ids))
        deleted_visitors = 0
        orphan = ~exists(select(Conversation.id).where(Conversation.visitor_id == Visitor.id))
        while True:
            visitor_ids = list(
                await session.scalars(select(Visitor.id).where(orphan).limit(batch_size))
            )
            if not visitor_ids:
                break
            await session.execute(delete(Visitor).where(Visitor.id.in_(visitor_ids)))
            await session.commit()
            deleted_visitors += len(visitor_ids)
            log.info("purge_visitor_batch", visitors=len(visitor_ids))
        log.info(
            "purge_complete",
            conversations=deleted_conversations,
            visitors=deleted_visitors,
        )
        return {"conversations": deleted_conversations, "visitors": deleted_visitors}


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Delete chats older than CHAT_RETENTION_DAYS.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(purge_expired(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
