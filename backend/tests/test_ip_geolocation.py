from typing import Any

import httpx
import pytest

from app.services.ip_geolocation import lookup_location


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

    location = await lookup_location("8.8.8.8", provider_url="https://geo.example.test/api/v1/json")

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
