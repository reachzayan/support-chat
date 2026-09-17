import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/api/internal/eval/turn",
        "/api/internal/eval/run",
        "/api/internal/playground/turn",
    ],
)
def test_temporary_internal_chat_routes_are_not_found(client, path: str) -> None:
    response = client.post(path, json={"site_key": "samplesite", "message": "hello"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
