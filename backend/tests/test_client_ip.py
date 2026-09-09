from ipaddress import IPv4Address

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.visitor import Visitor
from app.security.client_ip import resolve_client_ip
from tests.ws_helpers import (
    DEMO_PUBLIC_KEY,
    DEMO_SITE_KEY,
    insert_site,
    post_bootstrap,
    sync_session,
)

PEER = "10.1.2.3"
FORGED = "198.51.100.7"
CLIENT = "203.0.113.40"


def test_forged_forwarded_header_is_ignored_without_trusted_proxy() -> None:
    ip = resolve_client_ip(
        PEER,
        {"x-forwarded-for": FORGED, "forwarded": f"for={FORGED}"},
        trusted_cidrs=[],
    )
    assert ip == PEER


def test_trusted_proxy_uses_first_untrusted_hop() -> None:
    ip = resolve_client_ip(
        "10.0.0.2",
        {"x-forwarded-for": f"{CLIENT}, 10.0.0.8"},
        trusted_cidrs=["10.0.0.0/8"],
    )
    assert ip == CLIENT


def test_oversized_forwarded_header_falls_back_to_peer() -> None:
    hops = ", ".join([f"198.51.100.{index}" for index in range(1, 20)])
    ip = resolve_client_ip("10.0.0.2", {"x-forwarded-for": hops}, trusted_cidrs=["10.0.0.0/8"])
    assert ip == "10.0.0.2"


def test_bootstrap_stores_peer_ip_not_forged_header(client: TestClient) -> None:
    insert_site(DEMO_SITE_KEY, "Demo", DEMO_PUBLIC_KEY)
    client._transport.client = (PEER, 50000)
    response = post_bootstrap(
        client,
        extra_headers={"X-Forwarded-For": FORGED, "Forwarded": f"for={FORGED}"},
    )
    assert response.status_code == 200
    session = next(sync_session())
    try:
        visitor = session.scalars(select(Visitor)).one()
        assert visitor.ip == IPv4Address(PEER)
        assert visitor.ip != IPv4Address(FORGED)
    finally:
        session.close()
