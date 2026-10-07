from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.push_subscription import PushDelivery, PushSubscription
from app.models.user import User


class PushRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def subscribe(
        self, user: User, endpoint: str, p256dh: str, auth: str, silent: bool
    ) -> UUID:
        # Serialize device ownership changes, including concurrent first registration.
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "push-user-" + str(user.id)},
        )
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:endpoint, 0))"),
            {"endpoint": endpoint},
        )
        device = await self.session.scalar(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint).with_for_update()
        )
        if device is not None and (
            device.user_id != user.id or device.token_version != user.token_version
        ):
            await self.session.delete(device)
            await self.session.flush()
            device = None
        if device is None:
            count = len(
                (
                    await self.session.scalars(
                        select(PushSubscription.id).where(PushSubscription.user_id == user.id)
                    )
                ).all()
            )
            if count >= 20:
                raise ValueError("Device limit reached")
            device = PushSubscription(
                user_id=user.id, token_version=user.token_version, endpoint=endpoint
            )
            self.session.add(device)
        device.p256dh, device.auth, device.silent = p256dh, auth, silent
        await self.session.flush()
        return device.id

    async def unsubscribe(self, user_id: UUID, endpoint: str) -> None:
        await self.session.execute(
            delete(PushSubscription).where(
                PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint
            )
        )

    async def test(
        self, user_id: UUID, endpoint: str, preview: dict[str, str] | None = None
    ) -> bool:
        device = await self.session.scalar(
            select(PushSubscription).where(
                PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint
            )
        )
        if device is None:
            return False
        pending = await self.session.scalar(
            select(PushDelivery)
            .where(
                PushDelivery.subscription_id == device.id,
                PushDelivery.notification_id.is_(None),
                PushDelivery.finished_at.is_(None),
            )
            .limit(1)
            .with_for_update()
        )
        if pending is None:
            self.session.add(PushDelivery(subscription_id=device.id, preview=preview))
        else:
            pending.preview = preview
        return True
