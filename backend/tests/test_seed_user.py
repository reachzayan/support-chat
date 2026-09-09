from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.db import session_maker
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.security.passwords import verify_password
from scripts.seed_user import upsert_user

EMAIL = "agent@example.local"
FIRST_PASSWORD = "initial-secret15"
SECOND_PASSWORD = "rotated-secret15"


async def test_seed_user_password_overwrite_bumps_token_version_and_revokes_refresh(
    migrated_db,
) -> None:
    await upsert_user(EMAIL, "Alex Morgan", FIRST_PASSWORD, False)
    async with session_maker()() as session:
        user = (await session.execute(select(User).where(User.email == EMAIL))).scalar_one()
        assert user.token_version == 0
        session.add(
            RefreshToken(
                user_id=user.id,
                family_id=uuid4(),
                token_hash="a" * 64,
                expires_at=datetime.now(UTC) + timedelta(days=14),
            )
        )
        await session.commit()
        user_id = user.id

    await upsert_user(EMAIL, "Alex Morgan", SECOND_PASSWORD, False)

    async with session_maker()() as session:
        user = await session.get(User, user_id)
        assert user is not None
        assert user.token_version == 1
        assert verify_password(user.password_hash, SECOND_PASSWORD)
        assert not verify_password(user.password_hash, FIRST_PASSWORD)
        row = (
            await session.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
        ).scalar_one()
        assert row.revoked_at is not None
