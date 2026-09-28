from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, email: str, display_name: str, password_hash: str) -> User:
        user = User(
            email=normalize_email(email),
            display_name=display_name,
            password_hash=password_hash,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == normalize_email(email))
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def increment_token_version(self, user: User) -> None:
        user.token_version += 1
        await self._session.flush()

    async def token_state_for(self, ids: list[UUID]) -> dict[UUID, tuple[bool, int]]:
        if not ids:
            return {}
        result = await self._session.execute(
            select(User.id, User.is_active, User.token_version).where(User.id.in_(ids))
        )
        return {row.id: (bool(row.is_active), int(row.token_version)) for row in result.all()}
