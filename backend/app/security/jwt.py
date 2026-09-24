from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from app.settings import Settings

ACCESS_MINUTES = 15
ACCESS_ISSUER = "supportchat"
ACCESS_AUDIENCE = "supportchat-staff"


def create_access_token(user_id: UUID, token_version: int, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "token_version": token_version,
        "iss": ACCESS_ISSUER,
        "aud": ACCESS_AUDIENCE,
        "iat": now,
        "jti": str(uuid4()),
        "exp": now + timedelta(minutes=ACCESS_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        issuer=ACCESS_ISSUER,
        audience=ACCESS_AUDIENCE,
        options={"require": ["sub", "token_version", "iss", "aud", "iat", "jti", "exp"]},
    )
