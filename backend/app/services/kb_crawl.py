import ipaddress
import re
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import httpx

SITEMAP_DIRECTIVE_RE = re.compile(r"(?i)^sitemap:\s*(\S+)")

USER_AGENT = "SupportChatBot/1.0"
MAX_BYTES = 1_000_000
TIMEOUT = 10.0
MAX_HOPS = 3


class FetchError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _blocked(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or str(address) == "169.254.169.254"
    )


def _resolve_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    import socket

    found: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    try:
        for _family, _type, _proto, _canon, sockaddr in socket.getaddrinfo(host, None):
            found.append(ipaddress.ip_address(sockaddr[0]))
    except socket.gaierror as exc:
        raise FetchError("ssrf") from exc
    return found


def public_fetch_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
        raise FetchError("ssrf")
    host = parsed.hostname.casefold()
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and _blocked(literal):
        raise FetchError("ssrf")
    for address in _resolve_ips(host):
        if _blocked(address):
            raise FetchError("ssrf")
    return parsed


def allowed_fetch_url(url: str, allowed_hosts: set[str]):
    parsed = public_fetch_url(url)
    if parsed.hostname.casefold() not in allowed_hosts:
        raise FetchError("ssrf")
    return parsed


def fetch_html(url: str, allowed_hosts: set[str], hops: int = 0) -> str:
    return _fetch(url, allowed_hosts, hops, html_only=True)


def fetch_text(url: str, allowed_hosts: set[str], hops: int = 0) -> str:
    return _fetch(url, allowed_hosts, hops, html_only=False)


def robots_allows(url: str, robots_body: str, user_agent: str = USER_AGENT) -> bool:
    parser = RobotFileParser()
    parser.parse(robots_body.splitlines())
    return parser.can_fetch(user_agent, url)


def sitemap_urls_from_robots(robots_body: str) -> list[str]:
    found: list[str] = []
    for line in robots_body.splitlines():
        match = SITEMAP_DIRECTIVE_RE.match(line.strip())
        if match is None:
            continue
        loc = match.group(1).strip()
        if loc.lower().startswith("https://"):
            found.append(loc)
    return found


def parse_sitemap_locs(xml: str) -> list[str]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return []
    urls: list[str] = []
    for node in root.iter():
        tag = node.tag if isinstance(node.tag, str) else ""
        if not tag.endswith("loc"):
            continue
        loc = (node.text or "").strip()
        if loc.lower().startswith("https://"):
            urls.append(loc)
    return list(dict.fromkeys(urls))


def _read_body(response: httpx.Response) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_BYTES:
                raise FetchError("too_large")
        except ValueError:
            pass
    chunks: list[bytes] = []
    total = 0
    for piece in response.iter_bytes():
        total += len(piece)
        if total > MAX_BYTES:
            raise FetchError("too_large")
        chunks.append(piece)
    return b"".join(chunks)


def _fetch(url: str, allowed_hosts: set[str], hops: int, html_only: bool) -> str:
    parsed = allowed_fetch_url(url, allowed_hosts)
    if hops > MAX_HOPS:
        raise FetchError("http")
    try:
        with httpx.Client(
            timeout=TIMEOUT,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            with client.stream("GET", str(parsed.geturl())) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("http")
                    next_url = urljoin(str(parsed.geturl()), location)
                    return _fetch(next_url, allowed_hosts, hops + 1, html_only)
                if response.status_code != 200:
                    raise FetchError("http")
                content_type = response.headers.get("content-type", "")
                html_ok = "html" in content_type
                text_ok = content_type.startswith("text/") or "xml" in content_type
                if html_only and not html_ok:
                    raise FetchError("http")
                if not html_only and not html_ok and not text_ok:
                    raise FetchError("http")
                body = _read_body(response)
    except FetchError:
        raise
    except httpx.HTTPError as exc:
        raise FetchError("http") from exc
    # Postgres rejects NUL in UTF8 text; marketing HTML sometimes embeds it.
    return body.decode("utf-8", errors="replace").replace("\x00", "")
