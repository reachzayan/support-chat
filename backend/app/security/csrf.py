import hmac
import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.security.cookies import CSRF_COOKIE
from app.settings import Settings


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def require_csrf(request: Request) -> None:
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("x-csrf-token")
    if cookie is None or header is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF failed")
    try:
        matched = hmac.compare_digest(cookie, header)
    except (TypeError, ValueError):
        matched = False
    if not matched:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF failed")


def require_same_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlsplit(referer)
            if parsed.scheme and parsed.netloc:
                origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin != settings.staff_app_origin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF failed")
