from urllib.parse import urlparse, urlunparse

_HAS_SCHEME = "://"


def _flexible_parts(raw: str) -> tuple[str, str, str, str, str] | None:
    text = raw.strip()
    if not text or "*" in text:
        return None
    if _HAS_SCHEME not in text:
        text = f"https://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host.removeprefix("www.")
    if not host:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    port_text = "" if port is None else str(port)
    return parsed.scheme, host, port_text, parsed.path, parsed.query


def _netloc(host: str, port: str, scheme: str) -> str:
    if not port:
        return host
    if scheme == "https" and port in {"80", "443"}:
        return host
    if scheme == "http" and port == "80":
        return host
    return f"{host}:{port}"


def _stored_path(path: str) -> str:
    if path in ("", "/"):
        return ""
    return path.rstrip("/")


def canonicalize_https_url(raw: str) -> str | None:
    parts = _flexible_parts(raw)
    if parts is None:
        return None
    _scheme, host, port, path, query = parts
    netloc = _netloc(host, "" if port == "80" else port, "https")
    return urlunparse(("https", netloc, _stored_path(path), "", query, ""))


def canonicalize_http_url(raw: str) -> str | None:
    parts = _flexible_parts(raw)
    if parts is None:
        return None
    scheme, host, port, path, query = parts
    if scheme != "http":
        scheme = "https"
    netloc = _netloc(host, port, scheme)
    return urlunparse((scheme, netloc, _stored_path(path), "", query, ""))
