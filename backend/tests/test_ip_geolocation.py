from typing import Any

import httpx
import pytest

from app.services.ip_geolocation import lookup_location
from app.settings import Settings


def test_location_lookup_is_enabled_without_undocumented_environment_setup() -> None:
    settings = Settings(_env_file=None)
    assert settings.ip_geolocation_provider_url == "https://free.freeipapi.com/api/v1/json"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {
                "success": True,
                "cityName": "New York",
                "regionName": "New York",
                "countryName": "United States",
            },
            "New York, New York, United States",
        ),
        (
            {
                "success": True,
                "cityName": "",
                "regionName": "California",
                "countryName": "United States",
            },
            "California, United States",
        ),
        ({"error": "Rate limit exceeded"}, None),
        ({"success": True}, None),
    ],
)
async def test_lookup_location_reads_provider_response(monkeypatch, payload, expected) -> None:
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original_client(transport=transport, **kwargs)
    )
    assert (
        await lookup_location("8.8.8.8", provider_url="https://free.freeipapi.com/api/v1/json")
        == expected
    )


class _LocationResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {
            "cityName": "Mountain View",
            "regionName": "California",
            "countryName": "United States",
        }


class _LocationClient:
    def __init__(self, **_kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "_LocationClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def get(self, _url: str) -> _LocationResponse:
        return _LocationResponse()


@pytest.mark.asyncio
async def test_lookup_location_returns_city_region_and_country_from_a_public_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _LocationClient)

    location = await lookup_location("8.8.8.8", provider_url="https://example.com/geo")

    assert location == "Mountain View, California, United States"


@pytest.mark.asyncio
async def test_lookup_location_makes_no_outbound_request_without_explicit_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ForbiddenClient:
        def __init__(self, **_kwargs: Any) -> None:
            raise AssertionError("IP addresses must not leave the service by default")

    monkeypatch.setattr(httpx, "AsyncClient", _ForbiddenClient)

    assert await lookup_location("8.8.8.8", provider_url=None) is None


@pytest.mark.asyncio
async def test_lookup_location_does_not_call_loopback_or_link_local_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ForbiddenClient:
        def __init__(self, **_kwargs: Any) -> None:
            raise AssertionError("blocked provider hosts must not be fetched")

    monkeypatch.setattr(httpx, "AsyncClient", _ForbiddenClient)

    assert await lookup_location("8.8.8.8", provider_url="https://127.0.0.1/geo") is None
    assert await lookup_location("8.8.8.8", provider_url="https://169.254.169.254/latest") is None
