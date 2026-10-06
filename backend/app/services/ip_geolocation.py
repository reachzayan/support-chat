"""Best-effort location lookup for a public visitor IP."""

from ipaddress import ip_address
from typing import Any

import httpx

from app.services.kb_crawl import FetchError, public_fetch_url

LOOKUP_TIMEOUT_SECONDS = 3.0


def _location_from_payload(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    parts = [payload.get(field) for field in ("cityName", "regionName", "countryName")]
    values = [value.strip() for value in parts if isinstance(value, str) and value.strip()]
    return ", ".join(values) if values else None


async def lookup_location(raw_ip: str | None, *, provider_url: str | None) -> str | None:
    """Return city, region, country for a routable address without preventing chat creation."""
    if not provider_url:
        return None
    try:
        address = ip_address(raw_ip or "")
    except ValueError:
        return None
    if not address.is_global:
        return None
    try:
        public_fetch_url(provider_url)
    except FetchError:
        return None

    try:
        async with httpx.AsyncClient(timeout=LOOKUP_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{provider_url.rstrip('/')}/{address.compressed}")
            response.raise_for_status()
            return _location_from_payload(response.json())
    except (httpx.HTTPError, ValueError):
        return None
