"""Migration 47 applies today's import rules to canned rows imported before they existed.

Oracle: the LiveChat SampleSite/Sample Services library. Rows named in the rules change;
the roster, turnaround and other-website rows are the ones that must not.
"""

from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from tests.conftest import TEST_DATABASE_URL
from tests.ws_helpers import EASY_PUBLIC_KEY, HOST_ORIGIN, insert_site

SYNC_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def _insert(conn, site_id, shortcut: str, aliases: list[str] | None = None) -> None:
    conn.execute(
        text(
            "INSERT INTO canned_replies (site_id, shortcut, body, aliases) "
            "VALUES (:site, :shortcut, 'Body.', CAST(:aliases AS character varying[]))"
        ),
        {"site": site_id, "shortcut": shortcut, "aliases": aliases or []},
    )


def test_existing_rows_get_their_parents_hand_off_flags_and_bot_corrections(migrated_db) -> None:
    easy = insert_site("samplesite", "SampleSite", EASY_PUBLIC_KEY, [HOST_ORIGIN])
    other = insert_site("backgroundchecks", "Sample Services", "b" * 64, [HOST_ORIGIN])
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "46knowledgegaps")
    engine = create_engine(SYNC_URL)
    with engine.begin() as conn:
        for shortcut in (
            "der_what_is",
            "der_yes_followup",
            "der_no_followup",
            "der_not_sure_followup",
            "interpretation",
            "protected-2",
            "dispute-id",
            "verified-2",
            "driver_identifier_format",
            "greeting",
            "roster_update-2",
            "turnaround_results",
        ):
            _insert(conn, easy, shortcut)
        _insert(conn, easy, "help", aliases=["unable-verify"])
        _insert(conn, other, "der_yes_followup")

    command.upgrade(cfg, "head")

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT c.site_id, c.shortcut, c.bot_eligible, c.hands_off, p.shortcut "
                "FROM canned_replies c LEFT JOIN canned_replies p ON p.id = c.follows_id"
            )
        ).all()
    engine.dispose()

    by_scope = {(str(row[0]), row[1]): row[2:] for row in rows}
    easy_key, other_key = str(easy), str(other)
    # (bot_eligible, hands_off, follows shortcut)
    assert by_scope[(easy_key, "der_yes_followup")] == (True, False, "der_what_is")
    assert by_scope[(easy_key, "der_no_followup")] == (True, False, "der_what_is")
    assert by_scope[(easy_key, "der_not_sure_followup")] == (True, False, "der_what_is")
    assert by_scope[(other_key, "der_yes_followup")] == (True, False, None)
    assert by_scope[(easy_key, "interpretation")] == (True, True, None)
    assert by_scope[(easy_key, "protected-2")] == (True, True, None)
    assert by_scope[(easy_key, "dispute-id")] == (True, True, None)
    assert by_scope[(easy_key, "verified-2")] == (False, False, None)
    assert by_scope[(easy_key, "driver_identifier_format")] == (False, False, None)
    assert by_scope[(easy_key, "greeting")] == (False, False, None)
    assert by_scope[(easy_key, "help")] == (False, False, None)
    assert by_scope[(easy_key, "roster_update-2")] == (True, False, None)
    assert by_scope[(easy_key, "turnaround_results")] == (True, False, None)
