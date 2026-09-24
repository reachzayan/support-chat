from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories.kb_page_job_repo import KbPageJobRepository
from app.repositories.kb_snapshot_repo import KbSnapshotRepository


def _result() -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.all.return_value = []
    result.scalar_one_or_none.return_value = None
    return result


@pytest.mark.anyio
async def test_snapshot_history_is_bounded() -> None:
    session = AsyncMock()
    session.execute.return_value = _result()

    await KbSnapshotRepository(session).list_for_source(uuid4(), limit=25)

    statement = session.execute.await_args.args[0]
    assert statement._limit_clause is not None


@pytest.mark.anyio
async def test_source_snapshot_summaries_use_one_bounded_query() -> None:
    session = AsyncMock()
    session.execute.return_value = _result()
    source_ids = [uuid4(), uuid4()]

    summaries = await KbSnapshotRepository(session).summaries_for_sources(source_ids)

    assert summaries == {}
    assert session.execute.await_count == 1
    statement = session.execute.await_args.args[0]
    assert statement._limit_clause is not None
    assert statement._limit_clause.value == len(source_ids) * 2


@pytest.mark.anyio
async def test_progress_queries_bound_current_and_recent_jobs() -> None:
    session = AsyncMock()
    session.execute.side_effect = [_result(), _result()]

    current, recent = await KbPageJobRepository(session).progress_for_source(
        uuid4(), current_limit=50, recent_limit=20
    )

    assert current == []
    assert recent == []
    statements = [call.args[0] for call in session.execute.await_args_list]
    assert len(statements) == 2
    assert all(statement._limit_clause is not None for statement in statements)
