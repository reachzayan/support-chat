import ipaddress
from types import SimpleNamespace
from unittest.mock import patch

from app.services.kb_crawl import FetchError
from app.services.kb_fetcher import _allow_browser_request, fetch_page


async def test_loopback_does_not_invoke_crawler() -> None:
    called = {"n": 0}

    async def crawler(_url: str):
        called["n"] += 1
        return SimpleNamespace(success=True, html="<html></html>", url=_url)

    try:
        await fetch_page("https://127.0.0.1/", {"127.0.0.1"}, crawler=crawler)
        raised = False
    except FetchError as exc:
        raised = True
        assert exc.code == "ssrf"
    assert raised
    assert called["n"] == 0


async def test_missing_playwright_binary_fails_with_browser_error(monkeypatch) -> None:
    async def boom(_url: str, _allowed_hosts: set[str]):
        raise RuntimeError(
            "Executable doesn't exist at /tmp/playwright/chromium_headless_shell-1234/chrome"
        )

    def httpx_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
        return (
            "<html><body><main><h1>Turnaround</h1>"
            "<p>Most negative results are reported within 24-48 hours.</p>"
            "</main></body></html>"
        )

    monkeypatch.setattr("app.services.kb_fetcher._crawl4ai", boom)
    monkeypatch.setattr("app.services.kb_fetcher.fetch_html", httpx_fetch)
    try:
        await fetch_page("https://sample-site.example.com/faq", {"sample-site.example.com"})
        raised = False
    except FetchError as exc:
        raised = True
        assert exc.code == "browser"
    assert raised


def test_browser_request_guard_blocks_private_subresources() -> None:
    private = ipaddress.ip_address("127.0.0.1")
    with patch("app.services.kb_crawl._resolve_ips", return_value=[private]):
        try:
            _allow_browser_request("https://metadata.internal/latest", False, {"sample-site.example.com"})
            raised = False
        except FetchError as exc:
            raised = True
            assert exc.code == "ssrf"
    assert raised


def test_browser_request_guard_blocks_navigation_to_another_host() -> None:
    public = ipaddress.ip_address("1.1.1.1")
    with patch("app.services.kb_crawl._resolve_ips", return_value=[public]):
        try:
            _allow_browser_request(
                "https://untrusted.example/redirect", True, {"sample-site.example.com"}
            )
            raised = False
        except FetchError as exc:
            raised = True
            assert exc.code == "ssrf"
    assert raised


async def test_crawler_final_url_off_allowlist_is_ssrf() -> None:
    async def crawler(_url: str):
        return SimpleNamespace(
            success=True,
            html="<html><body>ok</body></html>",
            url="https://sample-services.example.com/faq",
            status_code=200,
        )

    try:
        await fetch_page(
            "https://sample-site.example.com/faq",
            {"sample-site.example.com"},
            crawler=crawler,
        )
        raised = False
    except FetchError as exc:
        raised = True
        assert exc.code == "ssrf"
    assert raised


async def test_crawler_redirected_url_off_allowlist_is_ssrf() -> None:
    async def crawler(_url: str):
        return SimpleNamespace(
            success=True,
            html="<html><body>ok</body></html>",
            url="https://sample-site.example.com/faq",
            redirected_url="https://sample-services.example.com/faq",
            status_code=200,
            response_headers={"content-type": "text/html; charset=utf-8"},
        )

    try:
        await fetch_page(
            "https://sample-site.example.com/faq",
            {"sample-site.example.com"},
            crawler=crawler,
        )
        raised = False
    except FetchError as exc:
        raised = True
        assert exc.code == "ssrf"
    assert raised


async def test_crawler_rejects_rendered_404_page() -> None:
    async def crawler(_url: str):
        return SimpleNamespace(
            success=True,
            html="<html><body>Not found</body></html>",
            url=_url,
            redirected_url=_url,
            status_code=404,
            response_headers={"content-type": "text/html"},
        )

    try:
        await fetch_page(
            "https://sample-site.example.com/missing",
            {"sample-site.example.com"},
            crawler=crawler,
        )
        raised = False
    except FetchError as exc:
        raised = True
        assert exc.code == "http_4xx"
    assert raised


async def test_crawler_rejects_non_html_response() -> None:
    async def crawler(_url: str):
        return SimpleNamespace(
            success=True,
            html="%PDF-1.7",
            url=_url,
            redirected_url=_url,
            status_code=200,
            response_headers={"content-type": "application/pdf"},
        )

    try:
        await fetch_page(
            "https://sample-site.example.com/brochure",
            {"sample-site.example.com"},
            crawler=crawler,
        )
        raised = False
    except FetchError as exc:
        raised = True
        assert exc.code == "non_html"
    assert raised


async def test_crawler_keeps_raw_markdown_when_fit_drops_product_copy() -> None:
    skip_trace = "Skip tracing covers nationwide addresses, scored phones, and right-party contact."
    public = ipaddress.ip_address("1.1.1.1")

    async def crawler(_url: str):
        return SimpleNamespace(
            success=True,
            html=(
                f"<html><body><main><h1>Collections</h1><p>{skip_trace}</p></main></body></html>"
            ),
            url=_url,
            redirected_url=_url,
            status_code=200,
            response_headers={"content-type": "text/html"},
            markdown=SimpleNamespace(
                raw_markdown=f"## Collections\n\n{skip_trace}",
                fit_markdown="## Collections\n\nCollection solutions are outreach tools.",
            ),
        )

    with patch("app.services.kb_crawl._resolve_ips", return_value=[public]):
        result = await fetch_page(
            "https://sample-data.example.com/collections",
            {"sample-data.example.com"},
            crawler=crawler,
        )
    assert result.markdown == f"## Collections\n\n{skip_trace}"
    assert "right-party contact" in result.markdown


async def test_crawler_falls_back_to_fit_markdown_when_raw_is_empty() -> None:
    public = ipaddress.ip_address("1.1.1.1")

    async def crawler(_url: str):
        return SimpleNamespace(
            success=True,
            html="<html><body><main><p>Most negative results are reported within 24-48 hours.</p></main></body></html>",
            url=_url,
            redirected_url=_url,
            status_code=200,
            response_headers={"content-type": "text/html"},
            markdown=SimpleNamespace(
                raw_markdown="   ",
                fit_markdown="Most negative results are reported within 24-48 hours.",
            ),
        )

    with patch("app.services.kb_crawl._resolve_ips", return_value=[public]):
        result = await fetch_page(
            "https://sample-site.example.com/faq",
            {"sample-site.example.com"},
            crawler=crawler,
        )
    assert result.markdown == "Most negative results are reported within 24-48 hours."


def test_crawl4ai_run_config_keeps_raw_html_markdown_without_pruning() -> None:
    from crawl4ai.content_filter_strategy import PruningContentFilter

    from app.services.kb_fetcher import crawler_run_config

    config = crawler_run_config()
    tags = config.excluded_tags or []
    assert "nav" in tags
    assert "header" not in tags
    assert "button" in tags
    assert "footer" not in tags
    assert "form" not in tags
    assert "aside" not in tags
    assert config.word_count_threshold <= 1
    assert config.wait_until == "load"
    assert config.delay_before_return_html >= 1.0
    assert config.scan_full_page is True
    assert config.remove_overlay_elements is True
    assert config.remove_consent_popups is True
    generator = config.markdown_generator
    assert generator is not None
    assert generator.content_filter is None
    assert not isinstance(generator.content_filter, PruningContentFilter)
    assert getattr(generator, "content_source", "") == "raw_html"
    markdown = generator.generate_markdown(
        '<body><p>Contact <a href="mailto:support@example.com">our team</a>.</p></body>',
        base_url="https://example.com",
    )
    assert "mailto:support@example.com" in markdown.raw_markdown
    assert (generator.options or {}).get("body_width") == 0
    assert (generator.options or {}).get("escape_html") is False


async def test_crawler_https_to_http_final_url_is_ssrf() -> None:
    public = ipaddress.ip_address("1.1.1.1")

    async def crawler(_url: str):
        return SimpleNamespace(
            success=True,
            html="<html></html>",
            url="http://sample-site.example.com/faq",
            status_code=200,
        )

    with patch("app.services.kb_crawl._resolve_ips", return_value=[public]):
        try:
            await fetch_page(
                "https://sample-site.example.com/faq",
                {"sample-site.example.com"},
                crawler=crawler,
            )
            raised = False
        except FetchError as exc:
            raised = True
            assert exc.code == "ssrf"
    assert raised
