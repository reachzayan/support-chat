import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.api.widget_bootstrap as widget_bootstrap_module
import app.chat.ws_agent as ws_agent_module
import app.chat.ws_visitor as ws_visitor_module
import app.main as main_module
from app.settings import Settings

STAFF_ORIGIN = "https://staff.chat.example.com"
WIDGET_ORIGIN = "https://widget.chat.example.com"
MARKETING_ORIGIN = "https://www.example.com"


def _production_settings() -> Settings:
    return Settings(
        app_env="production",
        database_url="postgresql://chat:chat@postgres:5432/support_chat",
        redis_url="rediss://app:strong-redis-password@redis:6379/0",
        jwt_secret="a8f3c1e9b2d64750c4a1f8e3b6d9027c5e1a4b8f3c6d9e2a7b0c5d8e1f4a7b3c",
        widget_token_secret=("d1e4a7b0c3f6d9e2a5b8c1d4e7f0a3b6c9d2e5f8a1b4c7d0e3f6a9b2c5d8e1f4"),
        rate_key_secret=("9c2f5a8d1e4b7c0f3a6d9e2b5c8f1a4d7e0b3c6f9a2d5e8b1c4f7a0d3e6b9c2f"),
        widget_csp_service_secret=(
            "e1a4b7c0d3f6a9b2c5d8e1f4a7b0c3d6e9f2a5b8c1d4e7f0a3b6c9d2e5f8a1b4c"
        ),
        cookie_secure=True,
        staff_app_origin=STAFF_ORIGIN,
        widget_origin=WIDGET_ORIGIN,
        marketing_host_origin=MARKETING_ORIGIN,
        trusted_proxy_cidrs="172.18.0.1/32",
        anthropic_api_key="sk-ant-test-not-a-real-key",
        openai_api_key="sk-test-not-a-real-key",
    )


@pytest.fixture
def production_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = _production_settings()
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(widget_bootstrap_module, "get_settings", lambda: settings)
    monkeypatch.setattr(ws_agent_module, "get_settings", lambda: settings)
    monkeypatch.setattr(ws_visitor_module, "get_settings", lambda: settings)
    return TestClient(main_module.create_app())


@pytest.mark.parametrize("host", ["widget.chat.example.com", "www.example.com"])
def test_non_staff_hosts_cannot_reach_staff_http_routes(
    production_client: TestClient,
    host: str,
) -> None:
    response = production_client.get("/auth/me", headers={"Host": host})

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


@pytest.mark.parametrize("host", ["staff.chat.example.com", "www.example.com"])
def test_non_widget_hosts_cannot_reach_widget_bootstrap(
    production_client: TestClient,
    host: str,
) -> None:
    response = production_client.post(
        "/api/public/widget-bootstrap",
        headers={"Host": host, "Origin": MARKETING_ORIGIN},
        content=b"",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_widget_host_can_reach_widget_bootstrap_route(
    production_client: TestClient,
) -> None:
    response = production_client.post(
        "/api/public/widget-bootstrap",
        headers={"Host": "widget.chat.example.com", "Origin": MARKETING_ORIGIN},
        content=b"",
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request"}


def test_public_hosts_cannot_reach_internal_widget_csp_route(
    production_client: TestClient,
) -> None:
    response = production_client.post(
        "/api/internal/widget-frame-ancestors",
        headers={
            "Host": "widget.chat.example.com",
            "X-SupportChat-Widget-CSP": "e1a4b7c0d3f6a9b2c5d8e1f4a7b0c3d6e9f2a5b8c1d4e7f0a3b6c9d2e5f8a1b4c",
        },
        content=b"",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


@pytest.mark.parametrize("path", ["/api/internal/dev/chat", "/api/internal/dev/trace"])
def test_temporary_chat_workbench_is_not_registered_in_production(
    production_client: TestClient,
    path: str,
) -> None:
    response = production_client.post(
        path,
        headers={"Host": "backend:8000"},
        json={"site_key": "samplesite", "message": "hello"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_widget_host_cannot_open_agent_socket_even_with_staff_origin(
    production_client: TestClient,
) -> None:
    with pytest.raises(WebSocketDisconnect) as closed:
        with production_client.websocket_connect(
            "/ws/agent",
            headers={"Host": "widget.chat.example.com", "Origin": STAFF_ORIGIN},
        ):
            pass

    assert closed.value.code == 4403


def test_staff_host_cannot_open_visitor_socket_even_with_widget_origin(
    production_client: TestClient,
) -> None:
    with pytest.raises(WebSocketDisconnect) as closed:
        with production_client.websocket_connect(
            "/ws/visitor",
            headers={"Host": "staff.chat.example.com", "Origin": WIDGET_ORIGIN},
        ):
            pass

    assert closed.value.code == 4403


def test_loopback_proxy_host_cannot_open_visitor_socket_even_with_widget_origin(
    production_client: TestClient,
) -> None:
    with pytest.raises(WebSocketDisconnect) as closed:
        with production_client.websocket_connect(
            "/ws/visitor",
            headers={"Host": "127.0.0.1:8000", "Origin": WIDGET_ORIGIN},
        ):
            pass

    assert closed.value.code == 4403
