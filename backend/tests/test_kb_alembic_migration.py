from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from tests.conftest import TEST_DATABASE_URL

SYNC_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def test_ingest_state_migration_round_trips(migrated_db) -> None:
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "14siteenabled")
    engine = create_engine(SYNC_URL)
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        }
        assert "kb_page_jobs" not in tables
        columns = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'kb_sources'"
                )
            )
        }
        assert "pages_discovered" not in columns
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        }
        assert "kb_page_jobs" in tables
        assert "kb_page_llm_extracts" in tables
        columns = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'kb_sources'"
                )
            )
        }
        assert "pages_discovered" in columns
        assert "stage" in columns
    engine.dispose()
