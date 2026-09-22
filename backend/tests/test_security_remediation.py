import ipaddress
from unittest.mock import patch

import httpx

from app.repositories.origins import canonicalize_origin
from app.security.passwords import verify_password
from app.services.app_log import format_log_dump_line
from app.services.kb_crawl import FetchError, _validated_addresses, fetch_html, parse_sitemap_locs


class _PinnedStreamClient:
    def __init__(self, *args, **kwargs):
        self.requested_url = None
        self.requested_headers = None
        self.requested_extensions = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, method, url, headers=None, extensions=None, **kwargs):
        self.requested_url = url
        self.requested_headers = headers
        self.requested_extensions = extensions
        response = httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<html></html>",
            request=httpx.Request(method, url),
        )

        class _Stream:
            def __enter__(self_inner):
                return response

            def __exit__(self_inner, *exit_args):
                return False

            def iter_bytes(self_inner):
                yield response.content

        return _Stream()


def test_canonicalize_origin_preserves_www() -> None:
    assert canonicalize_origin("https://www.sample-site.example.com") == "https://www.sample-site.example.com"
    assert canonicalize_origin("https://sample-site.example.com") == "https://sample-site.example.com"


def test_dns_rebinding_fetch_pins_public_ip() -> None:
    public = ipaddress.ip_address("93.184.216.34")

    def _client_factory(*args, **kwargs):
        return _PinnedStreamClient(*args, **kwargs)

    with patch("app.services.kb_crawl.httpx.Client", _client_factory):
        with patch("app.services.kb_crawl._validated_addresses", return_value=[public]):
            html = fetch_html("https://sample-site.example.com/faq", {"sample-site.example.com"})
    assert "<html>" in html


def test_dns_rebinding_rejects_private_resolved_ip() -> None:
    with patch(
        "app.services.kb_crawl._resolve_ips",
        return_value=[ipaddress.ip_address("10.0.0.4")],
    ):
        try:
            _validated_addresses("sample-site.example.com")
            raised = False
        except FetchError as exc:
            raised = True
            assert exc.code == "ssrf"
    assert raised


def test_parse_sitemap_locs_caps_url_count() -> None:
    xml = (
        "<urlset>"
        + "".join(f"<url><loc>https://sample-site.example.com/{i}</loc></url>" for i in range(10))
        + "</urlset>"
    )
    urls = parse_sitemap_locs(xml, max_urls=3)
    assert urls == [
        "https://sample-site.example.com/0",
        "https://sample-site.example.com/1",
        "https://sample-site.example.com/2",
    ]


def test_malformed_password_hash_returns_false() -> None:
    assert verify_password("not-a-real-hash", "secret") is False


def test_format_log_dump_line_escapes_newlines() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.models.app_log import AppLog

    row = AppLog(
        id=uuid4(),
        level="error",
        source="frontend",
        logger_name="ui",
        event="ui_window_error",
        message="line1\nforged=error event=admin",
        detail=None,
        created_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
    )
    line = format_log_dump_line(row)
    assert "\nforged=" not in line
    assert "line1\\nforged=error" in line
