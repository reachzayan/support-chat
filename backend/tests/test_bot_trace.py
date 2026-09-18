"""Diagnostics must not change normal model parsing or mix concurrent turns."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.llm.bot_responder import BotResponder
from app.services.bot_trace import capture_trace, record_trace
from app.services.grounded_response import EvidenceUnit, TurnContext


async def test_normal_provider_parsing_does_not_depend_on_diagnostic_serialization(monkeypatch):
    class Messages:
        async def create(self, **kwargs):
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="text", text="SampleMail handles", citations=[]),
                    SimpleNamespace(type="text", text="physical mail.", citations=[]),
                ],
                stop_reason="end_turn",
                _request_id="request-123",
            )

    class Client:
        def __init__(self, **kwargs):
            self.messages = Messages()

        async def close(self):
            return None

    monkeypatch.setattr("app.llm.bot_responder.AsyncAnthropic", Client)
    unit = EvidenceUnit(
        uuid4(),
        None,
        (),
        "SampleMail",
        "Managed physical mail",
        "SampleMail",
        "https://sample-data.example.com/samplemail",
    )
    draft = await BotResponder().generate_grounded_draft(
        TurnContext("What is SampleMail?", [unit]), [unit]
    )
    assert draft is not None
    assert draft.body == "SampleMail handles physical mail."
    assert draft.request_id == "request-123"
    await BotResponder.close_shared_client()


async def test_concurrent_captures_do_not_mix_or_survive_request_scope():
    async def turn(tag):
        with capture_trace() as trace:
            record_trace("decision", tag=tag)
            await asyncio.sleep(0)
            record_trace("decision", done=True)
            return trace

    first, second = await asyncio.gather(turn("first"), turn("second"))
    assert first == {"decision": {"tag": "first", "done": True}}
    assert second == {"decision": {"tag": "second", "done": True}}
    record_trace("decision", tag="outside")
    assert first["decision"]["tag"] == "first"
    assert second["decision"]["tag"] == "second"


async def test_trace_wait_timeout_keeps_background_task_running():
    from app.services.bot_trace import register_trace_task, wait_for_trace_tasks

    ready = asyncio.Event()

    async def summary():
        await ready.wait()
        record_trace("handoff_summary", status="completed")

    with capture_trace() as trace:
        task = asyncio.create_task(summary())
        register_trace_task(task)
        assert await wait_for_trace_tasks(timeout=0) == 1
        assert not task.cancelled()
        assert not task.done()
        ready.set()
        assert await wait_for_trace_tasks(timeout=1) == 0
        assert trace["handoff_summary"]["status"] == "completed"


async def test_trace_wait_is_scoped_to_its_own_request():
    from app.services.bot_trace import register_trace_task, wait_for_trace_tasks

    ready = asyncio.Event()
    with capture_trace():
        task = asyncio.create_task(ready.wait())
        register_trace_task(task)
        with capture_trace():
            assert await wait_for_trace_tasks(timeout=0) == 0
        ready.set()
        assert await wait_for_trace_tasks(timeout=1) == 0
