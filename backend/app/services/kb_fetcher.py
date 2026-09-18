from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
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
    title: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


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


def crawler_run_config() -> Any:
    from crawl4ai import CacheMode, CrawlerRunConfig, DefaultMarkdownGenerator

    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        check_robots_txt=False,
        verbose=False,
        word_count_threshold=1,
        page_timeout=30_000,
        wait_until="load",
        scan_full_page=True,
        scroll_delay=0.2,
        max_scroll_steps=20,
        delay_before_return_html=1.5,
        exclude_external_links=True,
        exclude_social_media_links=True,
        remove_overlay_elements=True,
        remove_consent_popups=True,
        flatten_shadow_dom=True,
        exclude_all_images=True,
        adjust_viewport_to_content=True,
        excluded_tags=[
            "script",
            "style",
            "noscript",
            "iframe",
            "nav",
            "button",
        ],
        markdown_generator=DefaultMarkdownGenerator(
            content_source="raw_html",
            options={
                "ignore_links": False,
                "ignore_mailto_links": False,
                "body_width": 0,
                "escape_html": False,
            },
        ),
    )


def _markdown_from_result(result: Any) -> str:
    markdown_obj = getattr(result, "markdown", "") or ""
    if hasattr(markdown_obj, "raw_markdown"):
        raw = str(markdown_obj.raw_markdown or "").strip()
        if raw:
            return raw
    if hasattr(markdown_obj, "fit_markdown"):
        fit = str(markdown_obj.fit_markdown or "").strip()
        if fit:
            return fit
    return str(markdown_obj)


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
    markdown = _markdown_from_result(result)
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
    title, metadata = _crawler_title_and_meta(result)
    return FetchResult(
        url=final_url,
        status=status,
        html=html,
        markdown=markdown,
        content_sha256=_digest(html),
        headers={str(key): str(value) for key, value in headers.items()},
        links=_internal_links(result, final_url),
        renderer="crawl4ai",
        title=title,
        metadata=metadata,
    )


def _crawler_title_and_meta(result: Any) -> tuple[str | None, dict[str, str]]:
    raw = getattr(result, "metadata", None) or {}
    if not isinstance(raw, dict):
        return None, {}
    metadata = {
        str(key): str(value)
        for key, value in raw.items()
        if key in {"title", "description"} and value
    }
    title = metadata.get("title")
    return title, metadata


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


@asynccontextmanager
async def page_crawler(allowed_hosts: set[str]) -> AsyncIterator[CrawlerFn]:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig
    except ImportError:

        async def missing(_url: str) -> Any:
            raise FetchError("browser")

        yield missing
        return
    browser = BrowserConfig(browser_type="chromium", headless=True, user_agent=USER_AGENT)
    blocked_navigation = False
    crawler = AsyncWebCrawler(config=browser)
    await crawler.__aenter__()
    try:

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

        async def crawl(url: str) -> Any:
            nonlocal blocked_navigation
            blocked_navigation = False
            result = await crawler.arun(url=url, config=crawler_run_config())
            if blocked_navigation:
                raise FetchError("ssrf")
            return result

        yield crawl
    finally:
        await crawler.__aexit__(None, None, None)


async def _crawl4ai(url: str, allowed_hosts: set[str]) -> Any:
    async with page_crawler(allowed_hosts) as crawl:
        return await crawl(url)


async def fetch_html_async(url: str, allowed_hosts: set[str]) -> str:
    return await asyncio.to_thread(fetch_html, url, allowed_hosts)


class LazyPageCrawler:
    def __init__(self, allowed_hosts: set[str]) -> None:
        self._hosts = allowed_hosts
        self._cm = None
        self._crawl: CrawlerFn | None = None

    async def fetch(self, url: str) -> Any:
        if self._crawl is None:
            self._cm = page_crawler(self._hosts)
            self._crawl = await self._cm.__aenter__()
        return await self._crawl(url)

    async def aclose(self) -> None:
        if self._cm is None:
            return
        await self._cm.__aexit__(None, None, None)
        self._cm = None
        self._crawl = None
