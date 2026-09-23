import pytest

from app.main import app
from app.models.user import User
from app.security.deps import get_current_admin


@pytest.fixture(params=[False, True], ids=["anonymous", "admin"])
def former_eval_client(client, monkeypatch, request):
    # Removed endpoints must stay unavailable, even under their former opt-in.
    monkeypatch.setenv("INTERNAL_EVAL_ENABLED", "true")
    if request.param:
        app.dependency_overrides[get_current_admin] = lambda: User(is_admin=True)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_admin, None)


@pytest.mark.parametrize(
    "path",
    [
        "/api/internal/eval/turn",
        "/api/internal/eval/run",
        "/api/internal/playground/turn",
        "/api/internal/dev/chat",
        "/api/internal/dev/trace",
    ],
)
def test_temporary_internal_chat_routes_are_not_found(former_eval_client, path: str) -> None:
    response = former_eval_client.post(path, json={"site_key": "samplesite", "message": "hello"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_temporary_internal_chat_routes_are_not_advertised(former_eval_client) -> None:
    response = former_eval_client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/api/internal/eval/turn" not in paths
    assert "/api/internal/eval/run" not in paths
    assert "/api/internal/playground/turn" not in paths
    assert "/api/internal/dev/chat" not in paths
    assert "/api/internal/dev/trace" not in paths
