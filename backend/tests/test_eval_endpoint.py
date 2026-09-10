from app.chat.outcome_copy import OFF_TOPIC_LINE
from tests.ws_helpers import EASY_PUBLIC_KEY, EASY_SITE_KEY, insert_site


def test_eval_turn_endpoint_runs_off_topic_without_widget_bootstrap(client) -> None:
    insert_site(EASY_SITE_KEY, "SampleSite", EASY_PUBLIC_KEY)
    response = client.post(
        "/api/internal/eval/turn",
        json={"site_key": EASY_SITE_KEY, "messages": ["I am sad"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "bot"
    assert payload["body"] == OFF_TOPIC_LINE
    assert payload["system_reason"] == "off_topic"
