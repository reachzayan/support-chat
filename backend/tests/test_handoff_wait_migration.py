"""Upgrade preserves live queues and retires previously closed chat alerts."""

from datetime import UTC, datetime

from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from app.db import session_maker
from app.repositories.notification_repo import NotificationRepository
from tests.bot_fixtures import insert_bot_conversation, insert_site
from tests.conftest import TEST_DATABASE_URL
from tests.ws_helpers import insert_staff


async def test_legacy_handoff_upgrade_preserves_wait_and_cleans_closed_alerts(migrated_db):
    insert_staff("legacy-wait@example.com", "Alex", "secret")
    started = datetime(2026, 10, 7, 12, tzinfo=UTC)
    async with session_maker()() as session:
        live = await insert_site(session, "live", "Live")
        callback = await insert_site(session, "callback", "Callback")
        callback.human_enabled = False
        _, waiting = await insert_bot_conversation(session, live)
        _, offline = await insert_bot_conversation(session, callback)
        _, closed = await insert_bot_conversation(session, live)
        repo = NotificationRepository(session)
        await repo.emit(waiting, "needs_attention", "legacy-wait")
        await repo.emit(closed, "needs_attention", "legacy-closed")
        waiting.state = offline.state = "queued"
        waiting.last_message_at = offline.last_message_at = started
        closed.state = "closed"
        await session.commit()
        waiting_id, callback_id, closed_id = waiting.id, offline.id, closed.id
    assert "test" in TEST_DATABASE_URL.rsplit("/", 1)[-1]
    engine = create_engine(TEST_DATABASE_URL.replace("+asyncpg", "+psycopg"))
    config = Config("alembic.ini")
    command.downgrade(config, "54pushpreview")
    try:
        command.upgrade(config, "head")
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT handoff_wait_started_at, handoff_wait_prompt_id FROM conversations WHERE id = :id"
                ),
                {"id": waiting_id},
            ).one()
            assert row == (started, None)
            assert (
                connection.execute(
                    text("SELECT handoff_wait_started_at FROM conversations WHERE id = :id"),
                    {"id": callback_id},
                ).scalar_one()
                is None
            )
            assert connection.execute(
                text(
                    "SELECT in_app, read_at IS NOT NULL FROM notifications WHERE conversation_id = :id"
                ),
                {"id": closed_id},
            ).one() == (False, True)
            assert connection.execute(
                text("SELECT in_app, read_at FROM notifications WHERE conversation_id = :id"),
                {"id": waiting_id},
            ).one() == (True, None)
    finally:
        command.upgrade(config, "head")
        engine.dispose()
