from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.settings import Settings

WIDGET_TOKEN_MINUTES = 5


def create_widget_token(
    site_id: UUID,
    visitor_id: UUID,
    conversation_id: UUID | None,
    parent_origin: str,
    settings: Settings,
) -> str:
    payload = {
        "typ": "widget",
        "site_id": str(site_id),
        "visitor_id": str(visitor_id),
        "parent_origin": parent_origin,
        "exp": datetime.now(UTC) + timedelta(minutes=WIDGET_TOKEN_MINUTES),
    }
    if conversation_id is not None:
        payload["conversation_id"] = str(conversation_id)
    return jwt.encode(payload, settings.widget_token_secret, algorithm="HS256")


def decode_widget_token(token: str, settings: Settings) -> dict:
    payload = jwt.decode(
        token,
        settings.widget_token_secret,
        algorithms=["HS256"],
        options={"require": ["exp"]},
    )
    if payload.get("typ") != "widget":
        raise jwt.InvalidTokenError("not a widget token")
    return payload
