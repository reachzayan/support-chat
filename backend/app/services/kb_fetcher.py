from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from app.services.kb_crawl import (
    MAX_BYTES,
    FetchError,
    allowed_fetch_url,
    fetch_html,
    public_fetch_url,
)

USER_AGENT = "SupportChatBot/1.0 (+https://sample-site.example.com/bots)"
_BROWSER_MARKERS = (
    "playwright",
    "executable doesn't exist",
    "browser has been closed",
    "chromium",
    "target closed",
)
_BROWSER_UNAVAILABLE_MARKERS = (
    "executable doesn't exist",
    "playwright install",
    "browser executable",
)


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    html: str
    markdown: str
    content_sha256: str
    headers: dict[str, str] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    links: tuple[str, ...] = ()
    renderer: str = "crawl4ai"


FetchFn = Callable[..., str | Awaitable[str]]
CrawlerFn = Callable[[str], Awaitable[Any]]


def _digest(html: str) -> str:
    return hashlib.sha256(html.encode()).hexdigest()


async def _call_fetch(fetch: FetchFn, url: str, allowed_hosts: set[str]) -> str:
    result = fetch(url, allowed_hosts)
    if hasattr(result, "__await__"):
        return await result  # type: ignore[misc]
    return str(result)


async def fetch_page(
    url: str,
    allowed_hosts: set[str],
    *,
    fetch: FetchFn | None = None,
    crawler: CrawlerFn | None = None,
) -> FetchResult:
    allowed_fetch_url(url, allowed_hosts)
    if fetch is not None:
        html = await _call_fetch(fetch, url, allowed_hosts)
        html = html.replace("\x00", "")
        return FetchResult(
            url=url,
            status=200,
            html=html,
            markdown="",
            content_sha256=_digest(html),
            renderer="injected",
        )
    if crawler is not None:
        result = await crawler(url)
        return _from_crawler_result(url, allowed_hosts, result)
    try:
        return _from_crawler_result(url, allowed_hosts, await _crawl4ai(url, allowed_hosts))
    except FetchError:
        raise
    except ImportError as exc:
        raise FetchError("browser") from exc
    except Exception as exc:
        raise FetchError(_browser_error_code(exc) if _is_browser_error(exc) else "http") from exc


def _is_browser_error(exc: BaseException) -> bool:
    text = str(exc).casefold()
    name = type(exc).__name__.casefold()
    return any(marker in text or marker in name for marker in _BROWSER_MARKERS)


def _browser_error_code(exc: BaseException) -> str:
    text = str(exc).casefold()
    if any(marker in text for marker in _BROWSER_UNAVAILABLE_MARKERS):
        return "browser"
    return "browser_crash"


def _from_crawler_result(requested: str, allowed_hosts: set[str], result: Any) -> FetchResult:
    final_url = str(
        getattr(result, "redirected_url", None) or getattr(result, "url", None) or requested
    )
    allowed_fetch_url(final_url, allowed_hosts)
    parsed = urlparse(final_url)
    if parsed.scheme != "https":
        raise FetchError("ssrf")
    success = bool(getattr(result, "success", True))
    if not success:
        message = str(getattr(result, "error_message", "") or "")
        error = RuntimeError(message)
        raise FetchError(_browser_error_code(error) if _is_browser_error(error) else "http")
    html = str(getattr(result, "html", None) or getattr(result, "cleaned_html", "") or "")
    markdown_obj = getattr(result, "markdown", "") or ""
    if hasattr(markdown_obj, "raw_markdown"):
        markdown = str(markdown_obj.raw_markdown or "")
    else:
        markdown = str(markdown_obj)
    html = html.replace("\x00", "")
    if len(html.encode("utf-8")) > MAX_BYTES:
        raise FetchError("too_large")
    status = int(getattr(result, "status_code", None) or 200)
    headers = dict(getattr(result, "response_headers", None) or {})
    if status == 429 or status >= 500:
        raise FetchError("http")
    if status >= 400:
        raise FetchError("http_4xx")
    content_type = next(
        (str(value) for key, value in headers.items() if str(key).casefold() == "content-type"),
        "",
    ).casefold()
    if (
        content_type
        and "text/html" not in content_type
        and "application/xhtml+xml" not in content_type
    ):
        raise FetchError("non_html")
    return FetchResult(
        url=final_url,
        status=status,
        html=html,
        markdown=markdown,
        content_sha256=_digest(html),
        headers={str(key): str(value) for key, value in headers.items()},
        links=_internal_links(result, final_url),
        renderer="crawl4ai",
    )


def _internal_links(result: Any, page_url: str) -> tuple[str, ...]:
    raw = getattr(result, "links", None) or {}
    items = raw.get("internal", []) if isinstance(raw, dict) else []
    found: list[str] = []
    for item in items:
        href = item.get("href") if isinstance(item, dict) else str(item)
        if not href:
            continue
        found.append(urljoin(page_url, str(href)))
    return tuple(dict.fromkeys(found))


def _allow_browser_request(url: str, is_navigation: bool, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme in {"about", "blob", "data"}:
        return
    if is_navigation:
        allowed_fetch_url(url, allowed_hosts)
    else:
        public_fetch_url(url)


async def _crawl4ai(url: str, allowed_hosts: set[str]) -> Any:
    try:
        from crawl4ai import (
            AsyncWebCrawler,
            BrowserConfig,
            CacheMode,
            CrawlerRunConfig,
            DefaultMarkdownGenerator,
        )
    except ImportError as exc:
        raise FetchError("browser") from exc
    browser = BrowserConfig(browser_type="chromium", headless=True, user_agent=USER_AGENT)
    run = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        check_robots_txt=False,
        verbose=False,
        word_count_threshold=1,
        page_timeout=30_000,
        wait_until="domcontentloaded",
        scan_full_page=True,
        scroll_delay=0.2,
        delay_before_return_html=0.3,
        exclude_external_links=True,
        excluded_tags=["script", "style"],
        markdown_generator=DefaultMarkdownGenerator(),
    )
    blocked_navigation = False
    async with AsyncWebCrawler(config=browser) as crawler:

        async def guard_page(page, **_kwargs):
            async def guard_route(route, request):
                nonlocal blocked_navigation
                try:
                    await asyncio.to_thread(
                        _allow_browser_request,
                        request.url,
                        request.is_navigation_request(),
                        allowed_hosts,
                    )
                except FetchError:
                    blocked_navigation = blocked_navigation or request.is_navigation_request()
                    await route.abort("blockedbyclient")
                    return
                await route.continue_()

            await page.route("**/*", guard_route)
            return page

        crawler.crawler_strategy.set_hook("on_page_context_created", guard_page)
        result = await crawler.arun(url=url, config=run)
        if blocked_navigation:
            raise FetchError("ssrf")
        return result


async def fetch_html_async(url: str, allowed_hosts: set[str]) -> str:
    return await asyncio.to_thread(fetch_html, url, allowed_hosts)
