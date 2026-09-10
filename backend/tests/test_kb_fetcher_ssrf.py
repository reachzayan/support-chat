import ipaddress
from types import SimpleNamespace
from unittest.mock import patch

from app.services.kb_crawl import FetchError
from app.services.kb_fetcher import fetch_page


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


async def test_missing_playwright_binary_falls_back_to_httpx(monkeypatch) -> None:
    async def boom(_url: str):
        raise RuntimeError(
            "Executable doesn't exist at /tmp/playwright/chromium_headless_shell-1234/chrome"
        )

    def httpx_fetch(url: str, _hosts: set[str], hops: int = 0) -> str:
        assert url == "https://sample-site.example.com/faq"
        return (
            "<html><body><main><h1>Turnaround</h1>"
            "<p>Most negative results are reported within 24-48 hours.</p>"
            "</main></body></html>"
        )

    monkeypatch.setattr("app.services.kb_fetcher._crawl4ai", boom)
    monkeypatch.setattr("app.services.kb_fetcher.fetch_html", httpx_fetch)
    result = await fetch_page("https://sample-site.example.com/faq", {"sample-site.example.com"})
    assert result.status == 200
    assert "24-48 hours" in result.html
    assert len(result.content_sha256) == 64


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
