import asyncio
import json
from uuid import uuid4

from app.chat import fanout


class _FakePubSub:
    def __init__(self, listen_impl) -> None:
        self._listen_impl = listen_impl

    async def subscribe(self, _channel: str) -> None:
        return None

    async def listen(self):
        async for item in self._listen_impl():
            yield item


class _FakeRedis:
    def __init__(self, listen_impl) -> None:
        self._listen_impl = listen_impl

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self._listen_impl)

    async def aclose(self) -> None:
        return None


async def test_publish_wakeup_has_a_hard_timeout(monkeypatch) -> None:
    cancelled = asyncio.Event()

    class _HungRedis:
        async def publish(self, _channel: str, _payload: str) -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    monkeypatch.setattr(fanout, "get_redis", lambda: _HungRedis())
    monkeypatch.setattr(fanout, "PUBLISH_TIMEOUT", 0.01)

    await asyncio.wait_for(fanout.publish_wakeup({"conversation_id": str(uuid4())}), timeout=0.2)
    assert cancelled.is_set()


async def test_subscriber_delivers_wakeup_after_listen_failure(monkeypatch) -> None:
    conversation_id = str(uuid4())
    delivered: list[dict] = []
    attempts = {"n": 0}

    async def listen_impl():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ConnectionError("dropped")
        yield {
            "type": "message",
            "data": json.dumps({"conversation_id": conversation_id, "site_key": "samplesite"}),
        }
        await asyncio.Event().wait()

    monkeypatch.setattr(
        fanout.redis.Redis,
        "from_url",
        staticmethod(lambda *_args, **_kwargs: _FakeRedis(listen_impl)),
    )
    monkeypatch.setattr(fanout, "RETRY_SLEEP", 0)

    async def capture(payload: dict) -> None:
        delivered.append(payload)

    monkeypatch.setattr(fanout.connection_manager, "deliver_wakeup", capture)

    await fanout.start_fanout()
    try:
        for _ in range(50):
            if delivered:
                break
            await asyncio.sleep(0.01)
        assert delivered == [{"conversation_id": conversation_id, "site_key": "samplesite"}]
    finally:
        await fanout.stop_fanout()
