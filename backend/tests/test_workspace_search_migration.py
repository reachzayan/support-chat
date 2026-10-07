"""The search index migration round-trips without changing application records."""

from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from tests.conftest import TEST_DATABASE_URL
from tests.ws_helpers import insert_site


def test_search_migration_round_trip_preserves_sites(migrated_db):
    site = insert_site("resume", "Résumé", "site-public-key")
    assert "test" in TEST_DATABASE_URL.rsplit("/", 1)[-1]
    config = Config("alembic.ini")
    engine = create_engine(TEST_DATABASE_URL.replace("+asyncpg", "+psycopg"))
    command.downgrade(config, "55handoffwait")
    try:
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT workspace_search_fold('Résumé ﬃrm')")).scalar_one()
                == "resume ffirm"
            )
            assert (
                connection.execute(
                    text("SELECT name FROM sites WHERE id=:id"), {"id": site}
                ).scalar_one()
                == "Résumé"
            )
            indexes = connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE indexname LIKE '%workspace_search' AND schemaname='public'"
                )
            )
            assert len(indexes.all()) == 9
    finally:
        command.upgrade(config, "head")
        engine.dispose()
