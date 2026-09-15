from tests.ws_helpers import EASY_PUBLIC_KEY, EASY_SITE_KEY, insert_site

CLARIFY_SCOPE = "What would you like to know about screening or compliance?"


def test_eval_turn_endpoint_returns_neutral_clarification_without_widget_bootstrap(client) -> None:
    insert_site(EASY_SITE_KEY, "SampleSite", EASY_PUBLIC_KEY)
    response = client.post(
        "/api/internal/eval/turn",
        json={"site_key": EASY_SITE_KEY, "messages": ["I am sad"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "bot"
    assert payload["body"] == CLARIFY_SCOPE
    assert payload["system_reason"] == "clarify"
