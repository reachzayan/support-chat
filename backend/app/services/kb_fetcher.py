from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.services.kb_crawl import FetchError, allowed_fetch_url, fetch_html

USER_AGENT = "SupportChatBot/1.0 (+https://sample-site.example.com/bots)"


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    html: str
    markdown: str
    content_sha256: str
    headers: dict[str, str] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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
        )
    if crawler is not None:
        result = await crawler(url)
        return _from_crawler_result(url, allowed_hosts, result)
    try:
        return _from_crawler_result(url, allowed_hosts, await _crawl4ai(url))
    except FetchError as exc:
        if exc.code != "browser":
            raise
    except Exception:
        pass
    html = await fetch_html_async(url, allowed_hosts)
    html = html.replace("\x00", "")
    return FetchResult(
        url=url,
        status=200,
        html=html,
        markdown="",
        content_sha256=_digest(html),
    )


def _from_crawler_result(requested: str, allowed_hosts: set[str], result: Any) -> FetchResult:
    final_url = str(getattr(result, "url", None) or requested)
    allowed_fetch_url(final_url, allowed_hosts)
    parsed = urlparse(final_url)
    if parsed.scheme != "https":
        raise FetchError("ssrf")
    success = bool(getattr(result, "success", True))
    if not success:
        raise FetchError("http")
    html = str(getattr(result, "html", None) or getattr(result, "cleaned_html", "") or "")
    markdown_obj = getattr(result, "markdown", "") or ""
    if hasattr(markdown_obj, "raw_markdown"):
        markdown = str(markdown_obj.raw_markdown or "")
    else:
        markdown = str(markdown_obj)
    html = html.replace("\x00", "")
    status = int(getattr(result, "status_code", None) or 200)
    headers = dict(getattr(result, "response_headers", None) or {})
    return FetchResult(
        url=final_url,
        status=status,
        html=html,
        markdown=markdown,
        content_sha256=_digest(html),
        headers={str(key): str(value) for key, value in headers.items()},
    )


async def _crawl4ai(url: str) -> Any:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except ImportError as exc:
        raise FetchError("browser") from exc
    browser = BrowserConfig(browser_type="chromium", headless=True, user_agent=USER_AGENT)
    run = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        check_robots_txt=False,
        verbose=False,
        word_count_threshold=1,
        page_timeout=30_000,
    )
    async with AsyncWebCrawler(config=browser) as crawler:
        return await crawler.arun(url=url, config=run)


async def fetch_html_async(url: str, allowed_hosts: set[str]) -> str:
    return await asyncio.to_thread(fetch_html, url, allowed_hosts)
