import ipaddress
from typing import ClassVar
from unittest.mock import patch

import httpx
import pytest

from app.services.kb_crawl import (
    MAX_HOPS,
    FetchError,
    allowed_fetch_url,
    fetch_html,
    pinned_get,
    public_fetch_url,
    robots_allows,
)

_PUBLIC = ipaddress.ip_address("1.1.1.1")
_PRIVATE = ipaddress.ip_address("10.0.0.4")


class _FakeStream:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self._response

    def __exit__(self, *args):
        return False

    def iter_bytes(self):
        yield self._response.content


class _RedirectStreamClient:
    def __init__(self, *args, redirect: httpx.Response, **kwargs):
        self._redirect = redirect

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, method, url, **kwargs):
        host = (kwargs.get("headers") or {}).get("Host")
        if host == "sample-site.example.com" and str(url).endswith("/start"):
            return _FakeStream(self._redirect)
        if url == "https://evil.internal/private" or (
            host == "evil.internal" and str(url).endswith("/private")
        ):
            return _FakeStream(
                httpx.Response(
                    200,
                    headers={"content-type": "text/html"},
                    content=b"<html></html>",
                    request=httpx.Request("GET", url),
                )
            )
        raise AssertionError(f"unexpected url {url}")


def _resolve_redirect_hosts(host: str):
    if host == "sample-site.example.com":
        return [_PUBLIC]
    if host == "evil.internal":
        return [_PRIVATE]
    raise FetchError("ssrf")


def test_loopback_https_is_ssrf() -> None:
    try:
        allowed_fetch_url("https://127.0.0.1/", {"sample-site.example.com"})
        raised = False
    except FetchError as exc:
        raised = True
        assert exc.code == "ssrf"
    assert raised


def test_samplesite_host_is_allowed_for_samplesite_site() -> None:
    public = ipaddress.ip_address("1.1.1.1")
    with patch("app.services.kb_crawl._resolve_ips", return_value=[public]):
        parsed = allowed_fetch_url("https://sample-site.example.com/faq", {"sample-site.example.com"})
    assert parsed.hostname == "sample-site.example.com"


def test_background_checks_host_rejected_on_samplesite_site() -> None:
    try:
        allowed_fetch_url("https://sample-services.example.com/", {"sample-site.example.com"})
        raised = False
    except FetchError as exc:
        raised = True
        assert exc.code == "ssrf"
    assert raised


def test_fetch_does_not_contact_loopback(monkeypatch) -> None:
    def _fail_get(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    monkeypatch.setattr("httpx.Client.get", _fail_get)
    try:
        fetch_html("https://127.0.0.1/", {"sample-site.example.com"})
        fetched = True
    except FetchError as exc:
        fetched = False
        assert exc.code == "ssrf"
    assert fetched is False


def test_allowlisted_hostname_with_private_resolved_ip_is_ssrf() -> None:
    with patch(
        "app.services.kb_crawl._resolve_ips", return_value=[ipaddress.ip_address("10.0.0.4")]
    ):
        try:
            allowed_fetch_url("https://sample-site.example.com/", {"sample-site.example.com"})
            raised = False
        except FetchError as exc:
            raised = True
            assert exc.code == "ssrf"
    assert raised


def test_mixed_public_and_private_a_records_is_ssrf() -> None:
    addresses = [
        ipaddress.ip_address("1.1.1.1"),
        ipaddress.ip_address("10.0.0.4"),
    ]
    with patch("app.services.kb_crawl._resolve_ips", return_value=addresses):
        try:
            allowed_fetch_url("https://sample-site.example.com/", {"sample-site.example.com"})
            raised = False
        except FetchError as exc:
            raised = True
            assert exc.code == "ssrf"
    assert raised


def test_relative_redirect_location_is_resolved_and_revalidated(monkeypatch) -> None:
    redirect = httpx.Response(
        302,
        headers={"location": "//evil.internal/private"},
        request=httpx.Request("GET", "https://sample-site.example.com/start"),
    )

    def _client_factory(*args, **kwargs):
        return _RedirectStreamClient(*args, redirect=redirect, **kwargs)

    monkeypatch.setattr("app.services.kb_crawl.httpx.Client", _client_factory)
    with patch("app.services.kb_crawl._resolve_ips", side_effect=_resolve_redirect_hosts):
        try:
            fetch_html("https://sample-site.example.com/start", {"sample-site.example.com", "evil.internal"})
            fetched = True
        except FetchError as exc:
            fetched = False
            assert exc.code == "ssrf"
    assert fetched is False


def test_robots_disallow_blocks_path() -> None:
    blocked = "User-agent: *\nDisallow: /\n"
    open_all = "User-agent: *\nDisallow:\n"
    url = "https://sample-site.example.com/faq"
    assert robots_allows(url, blocked) is False
    assert robots_allows(url, open_all) is True


def test_pinned_get_stops_redirect_loops(monkeypatch) -> None:
    calls = 0

    class LoopingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            nonlocal calls
            calls += 1
            if calls > MAX_HOPS + 1:
                raise AssertionError("redirect limit was not enforced")
            return httpx.Response(
                302,
                headers={"location": "/loop"},
                request=httpx.Request("GET", url),
            )

        def stream(self, method, url, **kwargs):
            return _FakeStream(self.get(url, **kwargs))

    monkeypatch.setattr("app.services.kb_crawl.httpx.Client", LoopingClient)
    monkeypatch.setattr("app.services.kb_crawl._resolve_ips", lambda _host: [_PUBLIC])

    with pytest.raises(FetchError) as caught:
        pinned_get("https://sample-site.example.com/loop", {"sample-site.example.com"})

    assert caught.value.code == "http"
    assert calls == MAX_HOPS + 1


@pytest.mark.parametrize(
    "url",
    [
        "https://100.64.0.1/",
        "https://[64:ff9b::7f00:1]/",
        "https://[::ffff:127.0.0.1]/",
        "https://sample-site.example.com:8443/",
    ],
)
def test_public_fetch_blocks_cgnat_nat64_mapped_and_non_443(url: str) -> None:
    with pytest.raises(FetchError) as caught:
        public_fetch_url(url)
    assert caught.value.code == "ssrf"


def test_pinned_get_rejects_oversized_stream_before_buffering(monkeypatch) -> None:
    class ChunkedResponse:
        status_code = 200
        headers: ClassVar = {"content-type": "text/html"}

        def iter_bytes(self):
            yield b"1234"
            yield b"5"

    class StreamingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *_args, **_kwargs):
            raise AssertionError("response bodies must not be buffered by Client.get")

        def stream(self, *_args, **_kwargs):
            return _FakeStream(ChunkedResponse())

    monkeypatch.setattr("app.services.kb_crawl.MAX_BYTES", 4)
    monkeypatch.setattr("app.services.kb_crawl.httpx.Client", StreamingClient)
    monkeypatch.setattr("app.services.kb_crawl._resolve_ips", lambda _host: [_PUBLIC])

    with pytest.raises(FetchError) as caught:
        pinned_get("https://sample-site.example.com/large", {"sample-site.example.com"})

    assert caught.value.code == "too_large"
