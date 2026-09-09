from collections.abc import Mapping
from ipaddress import ip_address, ip_network

MAX_HEADER_LEN = 512
MAX_HOPS = 8


def _as_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ip_address(value.strip().strip("[]")))
    except ValueError:
        return None


def _parse_xff(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_forwarded(value: str) -> list[str]:
    hops: list[str] = []
    for item in value.split(","):
        for piece in item.split(";"):
            field = piece.strip()
            if field.lower().startswith("for="):
                hops.append(field[4:].strip().strip('"'))
    return hops


def _hops_from_headers(headers: Mapping[str, str]) -> list[str]:
    forwarded = headers.get("forwarded") or headers.get("Forwarded") or ""
    xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For") or ""
    raw = forwarded or xff
    if len(raw) > MAX_HEADER_LEN:
        return []
    hops = _parse_forwarded(raw) if "for=" in raw.lower() else _parse_xff(raw)
    if len(hops) > MAX_HOPS:
        return []
    return hops


def _in_trusted(address: str, networks: list) -> bool:
    parsed = _as_ip(address)
    if parsed is None:
        return False
    addr = ip_address(parsed)
    return any(addr in network for network in networks)


def resolve_client_ip(
    peer: str | None,
    headers: Mapping[str, str],
    trusted_cidrs: list[str] | list,
) -> str | None:
    peer_ip = _as_ip(peer)
    networks = []
    for item in trusted_cidrs:
        if isinstance(item, str):
            raw = item.strip()
            if not raw:
                continue
            networks.append(ip_network(raw, strict=False))
        else:
            networks.append(item)
    if peer_ip is None or not networks or not _in_trusted(peer_ip, networks):
        return peer_ip
    hops = _hops_from_headers(headers)
    for hop in reversed(hops):
        candidate = _as_ip(hop)
        if candidate is None:
            continue
        if not _in_trusted(candidate, networks):
            return candidate
    return peer_ip
