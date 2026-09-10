import fnmatch
from urllib.parse import urljoin, urlparse, urlunparse
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_source import KbSource
from app.models.site import Site
from app.redis import get_redis
from app.services.kb_crawl import FetchError, fetch_html, fetch_text
from app.services.kb_embedder import Embedder

INGEST_KEY = "kb:ingest"
log = structlog.get_logger("kb_ingest")


class CanonicalError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def canonical_fetch_url(raw: str) -> str:
    parsed = urlparse(raw.strip())
    scheme = parsed.scheme.lower()
    if scheme != "https":
        raise CanonicalError("scheme_not_https")
    host = parsed.hostname.lower() if parsed.hostname else ""
    if not host:
        raise CanonicalError("scheme_not_https")
    default_ports = {"https": 443}
    port = "" if parsed.port in (None, default_ports.get(scheme)) else f":{parsed.port}"
    path = parsed.path or "/"
    return urlunparse((scheme, f"{host}{port}", path, "", parsed.query, ""))


def display_locator(raw: str) -> str | None:
    fragment = urlparse(raw).fragment
    return f"#{fragment}" if fragment else None


def canonical_url(url: str) -> str:
    try:
        return canonical_fetch_url(url)
    except CanonicalError:
        parsed = urlparse(url.strip())
        path = parsed.path or "/"
        return parsed._replace(path=path, fragment="").geturl()


async def enqueue_wakeup(source_id: UUID) -> None:
    try:
        await get_redis().rpush(INGEST_KEY, str(source_id))
    except Exception:
        log.info("ingest_wakeup_failed", source_id=str(source_id))


def allowed_hosts_for(site: Site, start_url: str) -> set[str]:
    hosts: set[str] = set()
    start_host = urlparse(start_url).hostname
    if start_host:
        folded = start_host.casefold()
        hosts.add(folded)
        if folded.startswith("www."):
            hosts.add(folded.removeprefix("www."))
        else:
            hosts.add(f"www.{folded}")
    for origin in site.allowed_origins:
        host = urlparse(origin).hostname
        if host:
            hosts.add(host.casefold())
    return hosts


def host_allowed(url: str, site: Site, start_url: str) -> bool:
    host = urlparse(url).hostname
    if host is None:
        return False
    return host.casefold() in allowed_hosts_for(site, start_url)


def path_under_prefix(url: str, start_url: str) -> bool:
    start = urlparse(start_url)
    parsed = urlparse(url)
    if parsed.hostname != start.hostname:
        return False
    start_path = start.path or "/"
    parsed_path = parsed.path or "/"
    if start_path == "/":
        return True
    if not parsed_path.startswith(start_path):
        return False
    if len(parsed_path) > len(start_path) and parsed_path[len(start_path)] != "/":
        return False
    return True


def path_depth(url: str, start_url: str) -> int:
    start = urlparse(start_url)
    parsed = urlparse(url)
    start_path = (start.path or "/").rstrip("/") or "/"
    parsed_path = parsed.path or "/"
    if not path_under_prefix(url, start_url):
        return -1
    if parsed_path == start_path or parsed_path == f"{start_path}/":
        return 0
    prefix = start_path
    remainder = parsed_path[len(prefix) :].lstrip("/")
    if not remainder:
        return 0
    return len([segment for segment in remainder.split("/") if segment])


def path_matches_globs(path: str, include_globs: list[str], exclude_globs: list[str]) -> bool:
    normalized = path or "/"
    if exclude_globs and any(fnmatch.fnmatch(normalized, pattern) for pattern in exclude_globs):
        return False
    if include_globs and not any(fnmatch.fnmatch(normalized, pattern) for pattern in include_globs):
        return False
    return True


def _url_allowed_by_source_rules(url: str, source: KbSource) -> bool:
    path = urlparse(url).path or "/"
    if source.mode == "prefix" and not path_under_prefix(url, source.start_url):
        return False
    if path_depth(url, source.start_url) > source.max_depth:
        return False
    return path_matches_globs(path, source.include_globs or [], source.exclude_globs or [])


def _same_prefix(url: str, start_url: str) -> bool:
    return path_under_prefix(url, start_url)


def _links_from(html: str, page_url: str) -> list[str]:
    from lxml import html as lxml_html

    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        return []
    found: list[str] = []
    for href in tree.xpath("//a/@href"):
        absolute = urljoin(page_url, str(href))
        try:
            canonical = canonical_fetch_url(absolute)
        except CanonicalError:
            continue
        found.append(canonical)
    return found


async def ingest_source(
    session: AsyncSession,
    source_id: UUID,
    embedder: Embedder | None = None,
    fetch=None,
    llm_client=None,
) -> None:
    from app.services.kb_pipeline import run_ingest

    await run_ingest(session, source_id, embedder=embedder, fetch=fetch, llm_client=llm_client)


def _plan_urls(source: KbSource) -> list[str]:
    if source.mode == "prefix":
        return [source.start_url]
    urls = list(source.seed_urls or [])
    if not urls:
        return [source.start_url]
    return list(dict.fromkeys(urls))


def _robots_body(url: str, hosts: set[str], fetch, cache: dict[str, str | None]) -> str | None:
    host = urlparse(url).hostname
    if host is None:
        return None
    key = host.casefold()
    if key in cache:
        return cache[key]
    robots_url = f"https://{key}/robots.txt"
    body = _try_fetch(robots_url, hosts, fetch)
    if body is None and fetch is fetch_html:
        body = _try_fetch(robots_url, hosts, fetch_text)
    cache[key] = body
    return body


def _try_fetch(url: str, hosts: set[str], fetch) -> str | None:
    try:
        return fetch(url, hosts)
    except (FetchError, KeyError):
        return None
