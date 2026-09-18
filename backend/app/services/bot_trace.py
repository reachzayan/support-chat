"""Request-scoped diagnostics for explicitly enabled, staff-only evaluations.

No transcript data is emitted to application logs. Outside a capture, recording
is a no-op. ContextVar keeps concurrent conversations' diagnostics separate.
"""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_current: ContextVar[dict[str, Any] | None] = ContextVar("bot_eval_trace", default=None)
_tasks: ContextVar[list[asyncio.Task[Any]] | None] = ContextVar("bot_eval_tasks", default=None)


@contextmanager
def capture_trace() -> Iterator[dict[str, Any]]:
    trace: dict[str, Any] = {}
    token = _current.set(trace)
    tasks_token = _tasks.set([])
    try:
        yield trace
    finally:
        _current.reset(token)
        _tasks.reset(tasks_token)


def record_trace(section: str, **fields: Any) -> None:
    trace = _current.get()
    if trace is not None:
        trace.setdefault(section, {}).update(fields)


def trace_active() -> bool:
    return _current.get() is not None


def register_trace_task(task: asyncio.Task[Any]) -> None:
    """Retain only background work started inside this evaluation capture."""
    tasks = _tasks.get()
    if tasks is not None:
        tasks.append(task)


async def wait_for_trace_tasks(*, timeout: float) -> int:
    """Bounded diagnostic wait; never cancel normal background work on timeout."""
    tasks = _tasks.get()
    if not tasks:
        return 0
    _, pending = await asyncio.wait(tasks, timeout=timeout)
    return len(pending)
