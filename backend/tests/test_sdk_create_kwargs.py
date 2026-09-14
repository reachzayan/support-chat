import inspect

from anthropic.resources.messages.messages import AsyncMessages

from app.llm.bot_responder import BotResponder


def test_grounded_messages_create_kwargs_match_installed_sdk() -> None:
    """Production create() kwargs must be accepted by the installed SDK."""
    signature = inspect.signature(AsyncMessages.create)
    allowed = set(signature.parameters)
    # Parameters BotResponder actually passes on the grounded path.
    production = {"model", "max_tokens", "system", "messages", "self"}
    assert production - {"self"} <= allowed
    assert "temperature" not in allowed or "temperature" not in production


def test_bot_responder_does_not_pass_temperature(monkeypatch) -> None:
    captured: dict = {}

    class FakeMessages:
        async def create(self, **kwargs):
            unexpected = set(kwargs) - set(inspect.signature(AsyncMessages.create).parameters)
            assert not unexpected, unexpected
            assert "temperature" not in kwargs
            captured.update(kwargs)
            block = type("Block", (), {"type": "text", "text": "ok", "citations": []})()
            return type("Response", (), {"content": [block]})()

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.messages = FakeMessages()

        async def close(self) -> None:
            return None

    monkeypatch.setattr("app.llm.bot_responder.AsyncAnthropic", FakeClient)
    BotResponder._shared_client = None
    BotResponder._shared_client_factory = None
