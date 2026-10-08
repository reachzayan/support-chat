import uuid

import pytest

from app.chat.outcome_copy import TRANSFER_OFFER, keep_helping_line
from app.db import session_maker
from app.llm.intent import (
    classify_sensitive,
    is_contact_request,
    is_escalate_request,
)
from app.llm.safety_markers import SensitiveCategory
from app.services.conversation_service import ConversationService
from app.services.grounded_response import _is_source_followup, history_recap_decision
from app.services.kb_embedder import FakeEmbedder
from tests.bot_fixtures import RecordingResponder, insert_bot_conversation, seed_brand_articles
from tests.ws_helpers import HOST_ORIGIN, message_count

PROCESS_QUESTIONS = [
    "Do you need a social security number to run a background check?",
    "Our order 123456789 is late",
    "Where do I take my drug test?",
    "How do I schedule my test?",
    "What time should I show up for the collection?",
    "What are the terms and conditions I agree to?",
    "What is the FCRA adverse action process?",
    "Do I need the candidate's driver's license number for an MVR check?",
    "Where do I find the case number on the portal?",
    "Do you store medical records?",
]


@pytest.mark.parametrize("text", PROCESS_QUESTIONS)
def test_process_questions_are_not_sensitive(text: str) -> None:
    assert classify_sensitive(text) is SensitiveCategory.NONE


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("My SSN is 123-45-6789", SensitiveCategory.SSN),
        ("my social security number is 123456789", SensitiveCategory.SSN),
        ("Please keep my SSN on file", SensitiveCategory.SSN),
        ("my license is A1234567", SensitiveCategory.DL),
        ("my driver's license number is 12345678", SensitiveCategory.DL),
        ("my date of birth is 01/02/1990", SensitiveCategory.DOB),
        ("medical record number 12345678", SensitiveCategory.MRN),
        ("specimen id 99887766", SensitiveCategory.SPECIMEN),
        ("my case number is 2024-55123", SensitiveCategory.SPECIMEN),
        ("what was my drug test result", SensitiveCategory.INDIVIDUAL_RESULT),
        ("did I pass my drug test", SensitiveCategory.INDIVIDUAL_RESULT),
        ("will my medication show up on my test", SensitiveCategory.MEDICAL_DETAIL),
        ("I take Xanax, will that show up", SensitiveCategory.MEDICAL_DETAIL),
        ("can I sue", SensitiveCategory.LEGAL_CASE),
        ("I want to dispute my report", SensitiveCategory.LEGAL_CASE),
        ("they took adverse action against me", SensitiveCategory.LEGAL_CASE),
        ("Can you look up this person's medical records?", SensitiveCategory.MEDICAL_DETAIL),
    ],
)
def test_shared_identifiers_and_personal_determinations_stay_sensitive(
    text: str, category: SensitiveCategory
) -> None:
    assert classify_sensitive(text) is category


@pytest.mark.parametrize(
    "text",
    ["Can I change the email address on my account?", "Do you verify phone numbers?"],
)
def test_generic_contact_words_are_not_contact_requests(text: str) -> None:
    assert is_contact_request(text) is False


@pytest.mark.parametrize(
    "text", ["Give me the specialist email please", "specialist phone number?"]
)
def test_specialist_contact_detail_is_not_a_handoff_request(text: str) -> None:
    assert is_escalate_request(text) is False


def test_real_handoff_requests_still_escalate() -> None:
    assert is_escalate_request("Give me a specialist") is True
    assert is_escalate_request("I want to talk to a human") is True


@pytest.mark.parametrize("text", ["Which page lists your pricing?", "What URL do I use to log in?"])
def test_new_questions_are_not_source_followups(text: str) -> None:
    assert _is_source_followup(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "which page is that from?",
        "Where did you get that?",
        "cite your source",
        "what's the source?",
        "which url was that?",
    ],
)
def test_references_to_prior_answer_are_source_followups(text: str) -> None:
    assert _is_source_followup(text) is True


def test_how_to_question_is_not_a_history_recap() -> None:
    prior = ({"role": "user", "content": "hello there"},)
    assert history_recap_decision("Remind me how to order a drug test", prior) is None
    assert history_recap_decision("remind me what I said", prior) is not None
    assert history_recap_decision("what did I tell you?", prior) is not None


@pytest.mark.parametrize("reply", ["no", "no thanks"])
async def test_declining_transfer_offer_gets_an_acknowledgement(migrated_db, reply: str) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        service = ConversationService(
            session, responder=RecordingResponder(), embedder=FakeEmbedder()
        )
        await service._insert_message(conversation, "system", TRANSFER_OFFER)
        await session.commit()
        result = await service.visitor_message(
            conversation.id, visitor.id, HOST_ORIGIN, uuid.uuid4(), reply
        )
        assert result.generation_id is None
        conversation_id = conversation.id
        ack = keep_helping_line(easy.name)

    assert message_count(conversation_id, role="system", body=ack) == 1


async def test_thanks_after_transfer_offer_gets_chitchat_reply(migrated_db) -> None:
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        visitor, conversation = await insert_bot_conversation(session, easy)
        await session.commit()
        service = ConversationService(
            session, responder=RecordingResponder(), embedder=FakeEmbedder()
        )
        await service._insert_message(conversation, "system", TRANSFER_OFFER)
        await session.commit()
        await service.visitor_message(
            conversation.id, visitor.id, HOST_ORIGIN, uuid.uuid4(), "thanks"
        )
        conversation_id = conversation.id

    assert (
        message_count(
            conversation_id,
            role="system",
            body="You're welcome. Anything else on screening or compliance?",
        )
        == 1
    )
