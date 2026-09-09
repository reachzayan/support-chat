import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.db import session_maker
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.user_repo import normalize_email
from app.security.passwords import hash_password

MIN_PASSWORD = 15


async def upsert_user(email: str, display_name: str, password: str, is_admin: bool) -> None:
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"password must be at least {MIN_PASSWORD} characters")
    normalized = normalize_email(email)
    async with session_maker()() as session:
        result = await session.execute(select(User).where(User.email == normalized))
        user = result.scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    email=normalized,
                    display_name=display_name,
                    password_hash=hash_password(password),
                    is_admin=is_admin,
                )
            )
        else:
            user.display_name = display_name
            user.password_hash = hash_password(password)
            user.is_admin = is_admin
            user.token_version += 1
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision an invited staff user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--admin", action="store_true")
    args = parser.parse_args()
    asyncio.run(upsert_user(args.email, args.display_name, args.password, args.admin))


if __name__ == "__main__":
    main()
