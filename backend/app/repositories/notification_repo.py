from uuid import UUID

from sqlalchemy import String, and_, any_, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import array, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.notification import (
    DEFAULT_PUSH_SCENARIOS,
    SCENARIOS,
    Notification,
    NotificationPreference,
    NotificationPushPreference,
)
from app.models.push_subscription import PushDelivery, PushSubscription
from app.models.site import Site
from app.models.user import User

DEFAULTS = {
    "live": True,
    "bot": False,
    "needs_attention": True,
    "visitor_message": True,
    "closed": False,
}


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def emit(
        self,
        conversation: Conversation,
        scenario: str,
        event_key: str,
        *,
        recipient_id: UUID | None = None,
        exclude_user_id: UUID | None = None,
    ) -> None:
        """Insert recipients with the chat transaction; never commit independently."""
        if scenario == "closed":
            await self.retire_conversation(conversation.id)
        in_app = func.coalesce(NotificationPreference.in_app, DEFAULTS[scenario])
        push = and_(
            func.coalesce(NotificationPushPreference.enabled, True).is_(True),
            literal(scenario)
            == any_(
                func.coalesce(
                    NotificationPushPreference.scenarios,
                    array(DEFAULT_PUSH_SCENARIOS, type_=String(32)),
                )
            ),
        )
        subscribed = (
            select(PushSubscription.id)
            .where(
                PushSubscription.user_id == User.id,
                PushSubscription.token_version == User.token_version,
            )
            .exists()
        )
        recipients = (
            select(
                User.id,
                literal(conversation.site_id),
                literal(conversation.id),
                literal(scenario),
                literal(event_key),
                in_app,
            )
            .outerjoin(
                NotificationPreference,
                and_(
                    NotificationPreference.user_id == User.id,
                    NotificationPreference.site_id == conversation.site_id,
                    NotificationPreference.scenario == scenario,
                ),
            )
            .outerjoin(
                NotificationPushPreference,
                and_(
                    NotificationPushPreference.user_id == User.id,
                    NotificationPushPreference.site_id == conversation.site_id,
                ),
            )
            .where(
                User.is_active.is_(True),
                or_(in_app.is_(True), and_(push, subscribed)),
            )
        )
        if recipient_id is not None:
            recipients = recipients.where(User.id == recipient_id)
        if exclude_user_id is not None:
            recipients = recipients.where(User.id != exclude_user_id)
        result = await self.session.execute(
            insert(Notification)
            .from_select(
                ["user_id", "site_id", "conversation_id", "scenario", "event_key", "in_app"],
                recipients,
            )
            .on_conflict_do_nothing(constraint="uq_notifications_event")
            .returning(Notification.id)
        )
        ids = result.scalars().all()
        if ids:
            await self.session.execute(
                insert(PushDelivery)
                .from_select(
                    ["notification_id", "subscription_id"],
                    select(Notification.id, PushSubscription.id)
                    .join(PushSubscription, PushSubscription.user_id == Notification.user_id)
                    .join(User, User.id == PushSubscription.user_id)
                    .outerjoin(
                        NotificationPushPreference,
                        and_(
                            NotificationPushPreference.user_id == Notification.user_id,
                            NotificationPushPreference.site_id == Notification.site_id,
                        ),
                    )
                    .where(
                        Notification.id.in_(ids),
                        User.token_version == PushSubscription.token_version,
                        push,
                    ),
                )
                .on_conflict_do_nothing(constraint="uq_push_delivery_event")
            )

    async def list_for_user(self, user_id: UUID, cursor: int | None, unread: bool) -> dict:
        active = select(Conversation.id).where(Conversation.state != "closed")
        visible = [
            Notification.user_id == user_id,
            Notification.in_app.is_(True),
            Notification.conversation_id.in_(active),
        ]
        filters = list(visible)
        if unread:
            filters.append(Notification.read_at.is_(None))
        if cursor is not None:
            filters.append(Notification.id < cursor)
        rows = (
            await self.session.execute(
                select(Notification, Site.name)
                .join(Site, Site.id == Notification.site_id)
                .where(*filters)
                .order_by(Notification.id.desc())
                .limit(31)
            )
        ).all()
        count = await self.session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                *visible,
                Notification.read_at.is_(None),
            )
        )
        unread_rows = (
            await self.session.execute(
                select(Notification.conversation_id, func.count())
                .where(
                    *visible,
                    Notification.read_at.is_(None),
                )
                .group_by(Notification.conversation_id)
            )
        ).all()
        return {
            "latest_id": await self.session.scalar(
                select(func.max(Notification.id)).where(Notification.user_id == user_id)
            ),
            "unread_conversations": {str(chat_id): count for chat_id, count in unread_rows},
            "items": [
                {
                    "id": row.id,
                    "site_id": row.site_id,
                    "site_name": name,
                    "conversation_id": row.conversation_id,
                    "scenario": row.scenario,
                    "created_at": row.created_at,
                    "read_at": row.read_at,
                }
                for row, name in rows[:30]
            ],
            "unread_count": count or 0,
            "next_cursor": rows[29][0].id if len(rows) > 30 else None,
        }

    async def retire_conversation(self, conversation_id: UUID) -> None:
        """Retire every recipient's stale alerts in the same transaction as closure."""
        await self.session.execute(
            update(Notification)
            .where(Notification.conversation_id == conversation_id)
            .values(in_app=False, read_at=func.coalesce(Notification.read_at, func.now()))
        )

    async def mark_read(self, user_id: UUID, notification_id: int) -> bool:
        result = await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.id == notification_id,
            )
            .values(read_at=func.coalesce(Notification.read_at, func.now()))
            .returning(Notification.id)
        )
        return result.scalar_one_or_none() is not None

    async def mark_all_read(self, user_id: UUID, through_id: int) -> None:
        await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.id <= through_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=func.now())
        )

    async def mark_conversation_read(
        self, user_id: UUID, conversation_id: UUID, through_id: int
    ) -> None:
        await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.conversation_id == conversation_id,
                Notification.id <= through_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=func.now())
        )

    async def preferences(self, user_id: UUID) -> list[dict]:
        sites = (
            await self.session.execute(select(Site.id, Site.name).order_by(Site.name, Site.id))
        ).all()
        overrides = (
            await self.session.scalars(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == user_id,
                )
            )
        ).all()
        values = {(row.site_id, row.scenario): row.in_app for row in overrides}
        push_rows = (
            await self.session.scalars(
                select(NotificationPushPreference).where(
                    NotificationPushPreference.user_id == user_id,
                )
            )
        ).all()
        push_values = {
            row.site_id: {"enabled": row.enabled, "scenarios": row.scenarios} for row in push_rows
        }
        return [
            {
                "site_id": site_id,
                "site_name": name,
                "scenarios": {
                    scenario: values.get((site_id, scenario), DEFAULTS[scenario])
                    for scenario in SCENARIOS
                },
                "push": push_values.get(
                    site_id, {"enabled": True, "scenarios": list(DEFAULT_PUSH_SCENARIOS)}
                ),
            }
            for site_id, name in sites
        ]

    async def save_preference(
        self, user_id: UUID, site_id: UUID, scenario: str, in_app: bool
    ) -> bool:
        if await self.session.get(Site, site_id) is None:
            return False
        await self.session.execute(
            insert(NotificationPreference)
            .values(
                user_id=user_id,
                site_id=site_id,
                scenario=scenario,
                in_app=in_app,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "site_id", "scenario"],
                set_={"in_app": in_app},
            )
        )
        return True

    async def save_push_preference(
        self, user_id: UUID, site_id: UUID, enabled: bool, scenarios: list[str]
    ) -> bool:
        if await self.session.get(Site, site_id) is None:
            return False
        await self.session.execute(
            insert(NotificationPushPreference)
            .values(
                user_id=user_id,
                site_id=site_id,
                enabled=enabled,
                scenarios=scenarios,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "site_id"],
                set_={"enabled": enabled, "scenarios": scenarios},
            )
        )
        return True
