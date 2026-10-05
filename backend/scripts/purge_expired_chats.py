import argparse
import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import delete, exists, func, or_, select

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
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
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
        orphan = ~exists(select(Conversation.id).where(Conversation.visitor_id == Visitor.id))
        visitor_count = int(
            await session.scalar(
                select(func.count())
                .select_from(Visitor)
                .where(or_(has_expired & ~has_kept, orphan & (Visitor.created_at < cutoff)))
            )
            or 0
        )
        counts = {"conversations": conversation_count, "visitors": visitor_count}
        if dry_run:
            log.info("purge_dry_run", conversations=conversation_count, visitors=visitor_count)
            return counts
        deleted_conversations = 0
        deleted_visitors = 0
        while True:
            rows = (
                await session.execute(
                    select(Conversation.id, Conversation.visitor_id)
                    .where(expired)
                    .order_by(Conversation.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            if not rows:
                break
            ids = [row.id for row in rows]
            await session.execute(delete(Conversation).where(Conversation.id.in_(ids)))
            # Remove identities belonging to the expired chats in the same transaction.
            removed = await session.scalars(
                delete(Visitor)
                .where(Visitor.id.in_([row.visitor_id for row in rows]), orphan)
                .returning(Visitor.id)
            )
            deleted_visitors += len(list(removed))
            await session.commit()
            deleted_conversations += len(ids)
            log.info("purge_batch", conversations=len(ids))
        # A fresh bootstrap intentionally has no conversation until prechat is submitted.
        expired_orphan = orphan & (Visitor.created_at < cutoff)
        while True:
            visitor_ids = list(
                await session.scalars(
                    select(Visitor.id)
                    .where(expired_orphan)
                    .order_by(Visitor.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            )
            if not visitor_ids:
                break
            removed = await session.scalars(
                delete(Visitor)
                .where(Visitor.id.in_(visitor_ids), expired_orphan)
                .returning(Visitor.id)
            )
            count = len(list(removed))
            await session.commit()
            deleted_visitors += count
            log.info("purge_visitor_batch", visitors=count)
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
