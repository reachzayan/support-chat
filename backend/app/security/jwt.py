from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.settings import Settings

ACCESS_MINUTES = 15


def create_access_token(user_id: UUID, token_version: int, settings: Settings) -> str:
    payload = {
        "sub": str(user_id),
        "token_version": token_version,
        "exp": datetime.now(UTC) + timedelta(minutes=ACCESS_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
