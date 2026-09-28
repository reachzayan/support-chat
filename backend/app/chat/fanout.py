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
MAX_ACTIVE_DELIVERIES = 32
INSTANCE_ID = uuid.uuid4().hex

_subscriber_task: asyncio.Task | None = None
_subscriber_client: redis.Redis | None = None
_delivery_tasks: dict[str, asyncio.Task] = {}
_pending_wakeups: dict[str, dict[str, Any]] = {}


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
    active_deliveries = list(_delivery_tasks.values())
    for task in active_deliveries:
        task.cancel()
    await asyncio.gather(*active_deliveries, return_exceptions=True)
    _delivery_tasks.clear()
    _pending_wakeups.clear()
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
            while True:
                message = await pubsub.get_message(timeout=15.0)
                if message is not None:
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
    if not isinstance(payload, dict):
        return
    try:
        conversation_id = str(uuid.UUID(str(payload["conversation_id"])))
    except (KeyError, ValueError, TypeError):
        return
    if payload.get("origin_instance") == INSTANCE_ID:
        return
    _pending_wakeups[conversation_id] = payload
    if conversation_id in _delivery_tasks:
        return
    if len(_delivery_tasks) >= MAX_ACTIVE_DELIVERIES:
        await asyncio.wait(_delivery_tasks.values(), return_when=asyncio.FIRST_COMPLETED)
    _delivery_tasks[conversation_id] = asyncio.create_task(_deliver_pending(conversation_id))


async def _deliver_pending(conversation_id: str) -> None:
    try:
        while payload := _pending_wakeups.pop(conversation_id, None):
            try:
                await connection_manager.deliver_wakeup(payload)
            except Exception:
                log.info("wakeup_delivery_failed", conversation_id=conversation_id)
    finally:
        _delivery_tasks.pop(conversation_id, None)
