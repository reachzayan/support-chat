from types import SimpleNamespace

from app.services.kb_alias import generate_aliases
from app.services.kb_extract.types import EvidenceUnit


async def test_information_blocks_never_receive_generated_question_aliases(monkeypatch) -> None:
    class Settings:
        anthropic_api_key = "configured-for-test"

    monkeypatch.setattr("app.services.kb_alias.get_settings", lambda: Settings())
    section = EvidenceUnit(
        kind="section",
        heading="Collection",
        canonical_question=None,
        answer_verbatim="View",
        body_for_search="Collection\nView",
        display_locator=None,
    )

    assert await generate_aliases(section) == ()


async def test_generated_aliases_keep_extracted_faq_wording(monkeypatch) -> None:
    class Settings:
        anthropic_api_key = "configured-for-test"

    class FakeMessages:
        async def create(self, **_kwargs):
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="text",
                        text='["Can I verify an account for collections?"]',
                    )
                ]
            )

    class FakeClient:
        def __init__(self, **_kwargs):
            self.messages = FakeMessages()

        async def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.kb_alias.get_settings", lambda: Settings())
    monkeypatch.setattr("anthropic.AsyncAnthropic", FakeClient)
    faq = EvidenceUnit(
        kind="faq",
        heading="Is verification compliant for collections and garnishment?",
        canonical_question="Is verification compliant for collections and garnishment?",
        answer_verbatim="Yes. Verification follows applicable requirements.",
        body_for_search="Verification compliance",
        display_locator=None,
        aliases=("Is verification compliant for collections?",),
    )

    assert await generate_aliases(faq) == (
        "Is verification compliant for collections?",
        "Can I verify an account for collections?",
    )
