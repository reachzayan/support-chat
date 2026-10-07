"""Oracle: existing queued tests survive the preview-content schema upgrade."""

import asyncio

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.models.push_subscription import PushDelivery, PushSubscription
from tests.conftest import TEST_DATABASE_URL
from tests.test_push_notifications import RecordingSender, deliver, subscription
from tests.ws_helpers import insert_staff


def test_legacy_pending_push_survives_upgrade_and_delivers(migrated_db):
    assert "test" in TEST_DATABASE_URL.rsplit("/", 1)[-1]
    user = insert_staff("legacy@example.com", "Legacy", "secret")
    data = subscription()
    engine = create_engine(TEST_DATABASE_URL.replace("+asyncpg", "+psycopg"))
    config = Config("alembic.ini")
    with Session(engine) as session:
        device = PushSubscription(
            user_id=user,
            token_version=0,
            endpoint=data["endpoint"],
            p256dh=data["keys"]["p256dh"],
            auth=data["keys"]["auth"],
            silent=False,
        )
        session.add(device)
        session.flush()
        session.add(PushDelivery(subscription_id=device.id))
        session.commit()
    command.downgrade(config, "53pushpreferences")
    try:
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT preview, attempts FROM push_deliveries")
            ).all() == [(None, 0)]
        sender = RecordingSender()
        assert asyncio.run(deliver(sender)) is True
        assert [item["title"] for item in sender.delivered] == ["SupportChat · Push notification test"]
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT finished_at IS NOT NULL FROM push_deliveries")
                ).scalar_one()
                is True
            )
    finally:
        command.upgrade(config, "head")
        engine.dispose()
