from urllib.parse import urlsplit

from app.settings import AppEnvironment, Settings

_INTERNAL_API_HOSTS = {"backend", "backend:8000", "127.0.0.1:8000", "localhost:8000"}


def _origin_host(origin: str) -> str:
    return urlsplit(origin).netloc.casefold()


def host_matches_origin(host: str | None, origin: str) -> bool:
    return bool(host) and host.casefold() == _origin_host(origin)


def websocket_surface_allowed(host: str | None, origin: str, settings: Settings) -> bool:
    if settings.app_env is not AppEnvironment.PRODUCTION:
        return True
    return host_matches_origin(host, origin)


def http_surface_allowed(path: str, host: str | None, settings: Settings) -> bool:
    if settings.app_env is not AppEnvironment.PRODUCTION:
        return True
    if path.startswith("/api/internal/"):
        return bool(host) and host.casefold() in _INTERNAL_API_HOSTS
    origin = (
        settings.widget_origin if path.startswith("/api/public/") else settings.staff_app_origin
    )
    return host_matches_origin(host, origin)
