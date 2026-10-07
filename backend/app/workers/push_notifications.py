import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy import delete, select

from app.db import session_maker
from app.models.conversation import Conversation
from app.models.notification import DEFAULT_PUSH_SCENARIOS, Notification, NotificationPushPreference
from app.models.push_subscription import PushDelivery, PushSubscription
from app.models.site import Site
from app.models.user import User
from app.services.push_content import preview_content, push_content
from app.services.web_push import WebPushSender, public_key
from app.settings import get_settings

log = structlog.get_logger("push_notifications")
_task: asyncio.Task | None = None


async def deliver_next(session, sender, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    job = await session.scalar(
        select(PushDelivery)
        .where(PushDelivery.finished_at.is_(None), PushDelivery.next_attempt_at <= now)
        .order_by(PushDelivery.next_attempt_at, PushDelivery.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return False
    device = await session.get(PushSubscription, job.subscription_id)
    user = await session.get(User, device.user_id) if device else None
    notification = (
        await session.get(Notification, job.notification_id) if job.notification_id else None
    )
    allowed = await _allowed(session, notification)
    if (
        not device
        or not user
        or not user.is_active
        or user.token_version != device.token_version
        or not allowed
        or now - job.created_at > timedelta(minutes=15)
    ):
        job.finished_at = now
        await session.commit()
        return True
    site = await session.get(Site, notification.site_id) if notification else None
    chat = await session.get(Conversation, notification.conversation_id) if notification else None
    content = (
        push_content(
            notification.scenario,
            site.name,
            notification.conversation_id,
            chat.inquiry_type if chat else None,
        )
        if notification and site
        else job.preview or preview_content()
    )
    payload = {
        "subscription_id": str(device.id),
        "notification_id": notification.id if notification else f"test-{job.id}",
        "conversation_id": str(notification.conversation_id) if notification else None,
        **content,
        "silent": device.silent,
    }
    job.attempts += 1
    try:
        status = await sender.send(device, payload)
    except (httpx.HTTPError, TimeoutError):
        status = 503
    if status in (404, 410):
        await session.execute(delete(PushSubscription).where(PushSubscription.id == device.id))
    elif 200 <= status < 300 or job.attempts >= 5 or (status < 500 and status != 429):
        job.finished_at = now
    else:
        job.next_attempt_at = now + timedelta(seconds=min(30 * 2 ** (job.attempts - 1), 600))
    await session.commit()
    return True


async def _allowed(session, notification: Notification | None) -> bool:
    if notification is None:
        return True
    if notification.read_at is not None:
        return False
    chat = await session.get(Conversation, notification.conversation_id)
    if chat is None or (chat.state == "closed" and notification.scenario != "closed"):
        return False
    preference = await session.get(
        NotificationPushPreference, (notification.user_id, notification.site_id)
    )
    if preference is None:
        return notification.scenario in DEFAULT_PUSH_SCENARIOS
    return preference.enabled and notification.scenario in preference.scenarios


async def _loop() -> None:
    # Row locks cover only delivery jobs; chat writes and read state remain independent.
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
        sender = WebPushSender(get_settings(), client)
        while True:
            try:
                async with session_maker()() as session:
                    if await deliver_next(session, sender):
                        continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("push_delivery_failed", error_class=type(exc).__name__)
            await asyncio.sleep(get_settings().background_job_poll_seconds)


async def start_push_notifications() -> None:
    global _task
    if public_key(get_settings()) and (_task is None or _task.done()):
        _task = asyncio.create_task(_loop())


async def stop_push_notifications() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
