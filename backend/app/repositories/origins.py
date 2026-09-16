from urllib.parse import urlparse


class InvalidOrigin(ValueError):
    pass


def _reject_origin_parts(parsed) -> None:
    if parsed.scheme not in ("http", "https"):
        raise InvalidOrigin("origin must be http or https")
    if parsed.username or parsed.password:
        raise InvalidOrigin("credentials are not allowed")
    if parsed.path not in ("", "/"):
        raise InvalidOrigin("origin must not include a path")
    if parsed.query or parsed.fragment:
        raise InvalidOrigin("origin must not include query or fragment")
    if parsed.hostname is None:
        raise InvalidOrigin("origin host is required")


def _format_origin(parsed, host: str) -> str:
    try:
        port = parsed.port
    except ValueError as exc:
        raise InvalidOrigin("invalid port") from exc
    if port is not None and (port < 1 or port > 65535):
        raise InvalidOrigin("invalid port")
    if (
        port is None
        or (parsed.scheme == "http" and port == 80)
        or (parsed.scheme == "https" and port == 443)
    ):
        return f"{parsed.scheme}://{host}"
    return f"{parsed.scheme}://{host}:{port}"


def canonicalize_origin(raw: str) -> str:
    if "*" in raw:
        raise InvalidOrigin("wildcard origins are not allowed")
    parsed = urlparse(raw)
    _reject_origin_parts(parsed)
    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise InvalidOrigin("invalid host") from exc
    return _format_origin(parsed, host)


def canonicalize_origins(origins: list[str]) -> list[str]:
    seen: list[str] = []
    for raw in origins:
        origin = canonicalize_origin(raw)
        if origin not in seen:
            seen.append(origin)
    return seen


def sanitize_visitor_url(raw: str, bound_origin: str, max_len: int = 2048) -> str:
    if not raw or len(raw) > max_len:
        raise InvalidOrigin("invalid url")
    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https"):
        raise InvalidOrigin("invalid url")
    if parsed.username or parsed.password:
        raise InvalidOrigin("invalid url")
    origin = canonicalize_origin(f"{parsed.scheme}://{parsed.netloc}")
    if origin != bound_origin:
        raise InvalidOrigin("origin mismatch")
    path = parsed.path if parsed.path else "/"
    return f"{origin}{path}"


def parent_origin(raw: str) -> str | None:
    text = raw.strip()
    if not text or "*" in text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        return None
    if parsed.hostname is None:
        return None
    try:
        return canonicalize_origin(f"{parsed.scheme}://{parsed.netloc}")
    except InvalidOrigin:
        return None
