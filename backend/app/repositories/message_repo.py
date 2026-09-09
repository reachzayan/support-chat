from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.user import User


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        conversation_id: UUID,
        role: str,
        body: str,
        client_message_id: UUID | None = None,
        author_user_id: UUID | None = None,
        source_article_ids: list[UUID] | None = None,
        source_chunk_ids: list[UUID] | None = None,
        snapshot_id: UUID | None = None,
        system_reason: str | None = None,
        source_urls: list[str] | None = None,
        display_locator: str | None = None,
        source_title: str | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            body=body,
            client_message_id=client_message_id,
            author_user_id=author_user_id,
            source_article_ids=source_article_ids,
            source_chunk_ids=source_chunk_ids,
            snapshot_id=snapshot_id,
            system_reason=system_reason,
            source_urls=source_urls,
            display_locator=display_locator,
            source_title=source_title,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_by_client_id(
        self, conversation_id: UUID, client_message_id: UUID
    ) -> Message | None:
        result = await self._session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.client_message_id == client_message_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_after(self, conversation_id: UUID, cursor: int) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.id > cursor)
            .order_by(Message.id)
        )
        return list(result.scalars().all())

    async def latest(self, conversation_id: UUID) -> Message | None:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def latest_visitor_body(self, conversation_id: UUID) -> str:
        result = await self._session.execute(
            select(Message.body)
            .where(Message.conversation_id == conversation_id, Message.role == "visitor")
            .order_by(Message.id.desc())
            .limit(1)
        )
        body = result.scalar_one_or_none()
        return body if body is not None else ""

    async def list_recent_roles(
        self, conversation_id: UUID, roles: set[str], limit: int
    ) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.role.in_(roles))
            .order_by(Message.id.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def list_for_conversation_with_authors(
        self, conversation_id: UUID
    ) -> list[tuple[Message, User | None]]:
        result = await self._session.execute(
            select(Message, User)
            .outerjoin(User, User.id == Message.author_user_id)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        )
        return [(message, author) for message, author in result.all()]
