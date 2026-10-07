"""Oracle: upgrading preserves old push choices and keeps existing inbox history visible."""

from uuid import uuid4

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.models.visitor import Visitor
from tests.conftest import TEST_DATABASE_URL
from tests.ws_helpers import insert_site, insert_staff


def test_upgrade_preserves_site_overrides_defaults_and_existing_inbox_history(migrated_db):
    assert "test" in TEST_DATABASE_URL.rsplit("/", 1)[-1]
    user = insert_staff("first@example.com", "First", "secret")
    other = insert_staff("other@example.com", "Other", "secret")
    easy = insert_site("easy", "SampleSite", "key")
    careers = insert_site("careers", "Careers", "other-key")
    config = Config("alembic.ini")
    engine = create_engine(TEST_DATABASE_URL.replace("+asyncpg", "+psycopg"))
    command.downgrade(config, "52webpush")
    try:
        with Session(engine) as session:
            visitor = Visitor(site_id=easy, resume_token_hash=uuid4().hex)
            session.add(visitor)
            session.flush()
            # This fixture represents schema 52, before today's ORM columns exist.
            chat_id = uuid4()
            session.execute(
                text(
                    "INSERT INTO conversations (id, site_id, visitor_id, state) "
                    "VALUES (:id, :site, :visitor, 'bot')"
                ),
                {"id": chat_id, "site": easy, "visitor": visitor.id},
            )
            session.execute(
                text(
                    "INSERT INTO notifications (user_id, site_id, conversation_id, scenario, event_key) "
                    "VALUES (:user, :site, :chat, 'live', 'history')"
                ),
                {"user": user, "site": easy, "chat": chat_id},
            )
            overrides = [
                (user, easy, "live", False),
                (user, easy, "bot", True),
                (user, easy, "closed", True),
                (other, easy, "needs_attention", False),
            ]
            overrides += [
                (user, careers, kind, False)
                for kind in ("live", "needs_attention", "visitor_message")
            ]
            for account, site, kind, enabled in overrides:
                session.execute(
                    text(
                        "INSERT INTO notification_preferences (user_id, site_id, scenario, in_app) "
                        "VALUES (:user, :site, :kind, :enabled)"
                    ),
                    {"user": account, "site": site, "kind": kind, "enabled": enabled},
                )
            session.commit()
        command.upgrade(config, "head")
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT user_id, site_id, enabled, scenarios FROM notification_push_preferences"
                )
            ).all()
            history = connection.execute(text("SELECT scenario, in_app FROM notifications")).all()
            original = connection.execute(
                text("SELECT user_id, site_id, scenario, in_app FROM notification_preferences")
            ).all()
        choices = {(row.user_id, row.site_id): (row.enabled, set(row.scenarios)) for row in rows}
        assert choices == {
            (user, easy): (True, {"bot", "needs_attention", "visitor_message", "closed"}),
            (user, careers): (True, set()),
            (other, easy): (True, {"live", "visitor_message"}),
        }
        assert history == [("live", True)]
        assert set(original) == set(overrides)
    finally:
        command.upgrade(config, "head")
        engine.dispose()
