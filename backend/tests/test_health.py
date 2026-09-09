from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_when_postgres_answers_select_one(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_degraded_when_redis_ping_fails(monkeypatch) -> None:
    from app.api import health as health_module

    class _FailingRedis:
        async def ping(self) -> bool:
            raise RuntimeError("could not connect")

    monkeypatch.setattr(health_module, "get_redis", lambda: _FailingRedis())
    response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded"}
    assert "could not connect" not in response.text
    assert "redis" not in response.text.lower()
    assert "56379" not in response.text


def test_health_returns_degraded_without_connection_details(monkeypatch) -> None:
    from app.api import health as health_module

    class _FailingConnect:
        async def __aenter__(self):
            raise RuntimeError("could not connect")

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class _FailingEngine:
        def connect(self) -> _FailingConnect:
            return _FailingConnect()

    monkeypatch.setattr(health_module, "get_engine", lambda: _FailingEngine())
    response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded"}
    assert "could not connect" not in response.text
    assert "postgres" not in response.text.lower()
    assert "127.0.0.1" not in response.text
