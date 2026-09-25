import asyncio
import json
import uuid
from typing import Any

import redis.asyncio as redis
import structlog

from app.chat.connection_manager import connection_manager
from app.redis import get_redis
from app.settings import get_settings

log = structlog.get_logger("fanout")
WAKEUP_CHANNEL = "chat:wakeup"
RETRY_SLEEP = 1.0
PUBLISH_TIMEOUT = 2.0
INSTANCE_ID = uuid.uuid4().hex

_subscriber_task: asyncio.Task | None = None
_subscriber_client: redis.Redis | None = None


async def publish_wakeup(payload: dict[str, Any]) -> None:
    try:
        outbound = {**payload, "origin_instance": INSTANCE_ID}
        await asyncio.wait_for(
            get_redis().publish(WAKEUP_CHANNEL, json.dumps(outbound)),
            timeout=PUBLISH_TIMEOUT,
        )
    except Exception:
        log.info("wakeup_publish_failed", conversation_id=payload.get("conversation_id"))


async def start_fanout() -> None:
    global _subscriber_task
    if _subscriber_task is not None and not _subscriber_task.done():
        return
    _subscriber_task = asyncio.create_task(_subscriber_loop())


async def stop_fanout() -> None:
    global _subscriber_task
    if _subscriber_task is not None:
        _subscriber_task.cancel()
        try:
            await _subscriber_task
        except asyncio.CancelledError:
            pass
        _subscriber_task = None
    await _close_subscriber_client()
    connection_manager.reset()


async def _close_subscriber_client() -> None:
    global _subscriber_client
    if _subscriber_client is None:
        return
    try:
        await _subscriber_client.aclose()
    except Exception:
        pass
    _subscriber_client = None


async def _subscriber_loop() -> None:
    global _subscriber_client
    while True:
        try:
            await _close_subscriber_client()
            _subscriber_client = redis.Redis.from_url(
                get_settings().redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=30,
                health_check_interval=15,
            )
            pubsub = _subscriber_client.pubsub()
            await pubsub.subscribe(WAKEUP_CHANNEL)
            async for message in pubsub.listen():
                await _handle_wakeup_message(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.info("wakeup_subscribe_failed", conversation_id=None)
            await _close_subscriber_client()
            await asyncio.sleep(RETRY_SLEEP)


async def _handle_wakeup_message(message: dict[str, Any]) -> None:
    if message.get("type") != "message":
        return
    data = message.get("data")
    if not isinstance(data, str):
        return
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return
    if "conversation_id" not in payload:
        return
    if payload.get("origin_instance") == INSTANCE_ID:
        return
    await connection_manager.deliver_wakeup(payload)
