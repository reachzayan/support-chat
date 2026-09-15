from sqlalchemy import create_engine, text

from tests.conftest import TEST_DATABASE_URL

SYNC_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def test_grounded_response_schema_is_unconditional_and_supports_span_citations(client) -> None:
    engine = create_engine(SYNC_URL)
    try:
        with engine.begin() as connection:
            columns = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'kb_chunks'"
                    )
                )
            }
            assert {
                "review_status",
                "reviewed_by",
                "reviewed_at",
                "review_note",
                "content_hash",
                "risk_class",
                "answer_mode",
                "topic_label",
            }.issubset(columns)
            tables = {
                row[0]
                for row in connection.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                )
            }
            assert "message_citations" in tables
            assert (
                connection.scalar(
                    text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_kb_chunks_grounded_trgm'")
                )
                == 1
            )
            site_flag = connection.scalar(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'sites' AND column_name = 'grounded_outcomes_v2'"
                )
            )
            assert site_flag is None
    finally:
        engine.dispose()
