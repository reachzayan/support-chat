from fastapi import Response

from app.settings import Settings

REFRESH_COOKIE = "supportchat_refresh"
CSRF_COOKIE = "supportchat_csrf"
REFRESH_MAX_AGE = 14 * 24 * 60 * 60


def set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=REFRESH_MAX_AGE,
        path="/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=REFRESH_MAX_AGE,
        path="/",
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        CSRF_COOKIE,
        path="/",
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )
