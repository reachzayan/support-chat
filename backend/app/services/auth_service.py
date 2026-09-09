import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.user_repo import UserRepository
from app.security.jwt import create_access_token
from app.security.passwords import hash_password, verify_password
from app.settings import Settings

REFRESH_DAYS = 14


class AuthFailed(Exception):
    pass


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    user: User


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._tokens = RefreshTokenRepository(session)

    async def login(self, email: str, password: str) -> SessionTokens:
        user = await self._users.get_by_email(email)
        if user is None or not user.is_active or not verify_password(user.password_hash, password):
            raise AuthFailed
        return await self._issue_session(user, uuid4())

    async def refresh(self, raw_token: str) -> SessionTokens:
        row = await self._tokens.get_by_hash(hash_refresh_token(raw_token))
        now = datetime.now(UTC)
        if row is None or row.revoked_at is not None or row.expires_at <= now:
            raise AuthFailed
        if row.replaced_at is not None:
            await self._tokens.revoke_family(row.family_id)
            await self._session.commit()
            raise AuthFailed
        user = await self._users.get_by_id(row.user_id)
        if user is None or not user.is_active:
            raise AuthFailed
        await self._tokens.mark_replaced(row)
        return await self._issue_session(user, row.family_id)

    async def logout(self, raw_token: str | None) -> None:
        if raw_token is None:
            return
        row = await self._tokens.get_by_hash(hash_refresh_token(raw_token))
        if row is None:
            return
        await self._tokens.revoke_family(row.family_id)
        user = await self._users.get_by_id(row.user_id)
        if user is not None:
            await self._users.increment_token_version(user)
        await self._session.commit()

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(user.password_hash, current_password):
            raise AuthFailed
        user.password_hash = hash_password(new_password)
        await self._users.increment_token_version(user)
        await self._tokens.revoke_all_for_user(user.id)
        await self._session.commit()

    async def _issue_session(self, user: User, family_id: UUID) -> SessionTokens:
        raw = new_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(days=REFRESH_DAYS)
        await self._tokens.create(user.id, family_id, hash_refresh_token(raw), expires_at)
        await self._session.commit()
        await self._session.refresh(user)
        access = create_access_token(user.id, user.token_version, self._settings)
        return SessionTokens(access_token=access, refresh_token=raw, user=user)
