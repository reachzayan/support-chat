"""Real conversation/database flows with recorded external provider responses."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from anthropic.types import Message as ProviderMessage
from sqlalchemy import select

from app.db import session_maker
from app.llm.bot_responder import BotResponder
from app.models.message import Message
from app.models.message_citation import MessageCitation
from app.models.user import User
from app.services.bot_trace import capture_trace
from app.services.conversation_service import ConversationService
from tests.bot_fixtures import insert_bot_conversation, insert_chunk, insert_site
from tests.ws_helpers import HOST_ORIGIN

WORKFLOW = "Candidates receive an authorization and choose a nearby collection site, usually without an appointment."
CONTACT = "To discuss pricing with a specialist, email inquiries@sample-site.example.com."
CTA = "Talk to a specialist or jump into the portal."


class OfflineEmbedding:
    async def embed_query(self, _text):
        return None


class RecordedProvider:
    def __init__(self, request, answer, proof, assessment, fail_stage=None):
        self.request, self.answer, self.proof = request, answer, proof
        self.assessment, self.fail_stage = assessment, fail_stage
        self.calls = []
        self.messages = self

    async def close(self):
        pass

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        stage = kwargs.get("tool_choice", {}).get("name")
        if stage == self.fail_stage and stage is not None:
            raise TimeoutError("recorded provider timeout")
        if stage:
            value = self.request if stage == "resolve_request" else self.assessment
            if isinstance(value, list):
                value = value.pop(0)
            return SimpleNamespace(
                stop_reason="tool_use",
                content=[SimpleNamespace(type="tool_use", name=stage, input=value)],
            )
        documents = [
            block
            for message in kwargs["messages"]
            if isinstance(message["content"], list)
            for block in message["content"]
            if block.get("type") == "document"
        ]
        citations = []
        if self.proof:
            for index, document in enumerate(documents):
                source = document["source"]["data"]
                if self.proof in source:
                    start = source.index(self.proof)
                    citations = [
                        {
                            "type": "char_location",
                            "document_index": index,
                            "document_title": document["title"],
                            "start_char_index": start,
                            "end_char_index": start + len(self.proof),
                            "cited_text": self.proof,
                        }
                    ]
                    break
            assert citations, "The supporting passage was not retrieved"
        return ProviderMessage.model_validate(
            {
                "id": "msg_relevance_replay",
                "type": "message",
                "role": "assistant",
                "model": "recorded",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": self.answer, "citations": citations}],
                "usage": {"input_tokens": 100, "output_tokens": 30},
            }
        )


def request(query, *, relation="standalone", intent="information", ambiguity=""):
    return {"query": query, "relation": relation, "intent": intent, "ambiguity": ambiguity}


async def run_chat(
    monkeypatch, provider, question, *, history=False, with_evidence=True, prior_misses=0
):
    await BotResponder.close_shared_client()
    monkeypatch.setattr("app.llm.bot_responder.AsyncAnthropic", lambda **_kwargs: provider)
    async with session_maker()() as session:
        site = await insert_site(session, "relevance-" + uuid4().hex[:8], "SampleSite Support")
        workflow = await insert_chunk(session, site, "Candidate collection appointment", WORKFLOW)
        if with_evidence:
            await insert_chunk(session, site, "Specialist pricing appointment contact", CONTACT)
            await insert_chunk(
                session, site, "Specialist portal", "No more chasing clinics. " + CTA
            )
        else:
            workflow.enabled = False
        visitor, conversation = await insert_bot_conversation(session, site)
        conversation.fallback_count = prior_misses
        if history:
            staff = User(
                email="review@local.test", display_name="Specialist", password_hash="unused"
            )
            session.add(staff)
            await session.flush()
            for role, body in [
                ("visitor", "Can I get pricing on drug testing?"),
                ("agent", "We can discuss a quote with you."),
                ("visitor", "how do i set up appointment"),
            ]:
                session.add(
                    Message(
                        conversation_id=conversation.id,
                        site_id=site.id,
                        role=role,
                        body=body,
                        client_message_id=uuid4(),
                        author_user_id=staff.id if role == "agent" else None,
                    )
                )
            previous = Message(
                conversation_id=conversation.id,
                site_id=site.id,
                role="bot",
                body=WORKFLOW,
                source_chunk_ids=[workflow.id],
                snapshot_id=workflow.snapshot_id,
                system_reason="answer",
            )
            session.add(previous)
            await session.flush()
            session.add(
                MessageCitation(
                    message=previous,
                    site_id=site.id,
                    chunk_id=workflow.id,
                    snapshot_id=workflow.snapshot_id,
                    response_start=0,
                    response_end=len(WORKFLOW),
                    source_start=0,
                    source_end=len(WORKFLOW),
                    cited_text=WORKFLOW,
                    source_title="Candidate collection appointment",
                    source_url="https://legacy.test/dot",
                )
            )
        await session.commit()
        service = ConversationService(session, embedder=OfflineEmbedding())
        submitted = await service.visitor_message(
            conversation.id, visitor.id, HOST_ORIGIN, uuid4(), question
        )
        assert submitted.generation_id is not None
        with capture_trace() as trace:
            await service.run_bot_turn(conversation.id, submitted.generation_id)
        row = await session.scalar(
            select(Message)
            .where(Message.conversation_id == conversation.id, Message.role == "bot")
            .order_by(Message.id.desc())
            .limit(1)
        )
        result = row.body, row.response_outcome, row.response_reason_code, conversation.state, trace
        trace["persisted_fallback_count"] = conversation.fallback_count
        trace["persisted_citation_count"] = len(row.citations)
    await BotResponder.close_shared_client()
    return result


async def test_specialist_correction_uses_resolved_request_without_carrying_wrong_workflow(
    migrated_db, monkeypatch
):
    provider = RecordedProvider(
        request(
            "specialist pricing appointment contact", relation="correction", intent="appointment"
        ),
        CONTACT,
        CONTACT,
        {"status": "supported_next_step", "reason": "responsive"},
    )
    body, outcome, reason, state, trace = await run_chat(
        monkeypatch, provider, "i meant with specialist", history=True, prior_misses=1
    )
    assert body == CONTACT
    assert (outcome, reason, state) == ("partial_answer", "supported_next_step", "bot")
    assert trace["persisted_fallback_count"] == 0
    assert CONTACT in str(trace["retrieval"]["evidence"])
    assert trace["retrieval"]["query"] == "specialist pricing appointment contact"
    assert trace["retrieval"]["carried_evidence_ids"] == []
    assert "We can discuss a quote with you." in str(provider.calls[0]["messages"])
    assert "i meant with specialist" in str(provider.calls[1]["messages"][-1])


async def test_ambiguous_enrollment_asks_before_assuming_candidate_workflow(
    migrated_db, monkeypatch
):
    clarification = "Do you mean opening an employer account, or sending a candidate for a test?"
    provider = RecordedProvider(
        request(
            "employer account enrollment candidate testing",
            intent="account_setup",
            ambiguity="Employer account setup or ordering a candidate test",
        ),
        clarification,
        None,
        {"status": "clarification", "reason": "responsive"},
    )
    body, outcome, _, state, _ = await run_chat(
        monkeypatch, provider, "what is the enrollment process"
    )
    assert body == clarification
    assert (outcome, state) == ("clarification", "bot")


async def test_cited_wrong_workflow_is_rejected_before_persistence(migrated_db, monkeypatch):
    provider = RecordedProvider(
        request(
            "candidate appointment employer enrollment",
            intent="account_setup",
        ),
        WORKFLOW,
        WORKFLOW,
        {"status": "reject", "reason": "wrong_action"},
    )
    body, outcome, reason, _, trace = await run_chat(
        monkeypatch, provider, "what is the enrollment process"
    )
    assert body != WORKFLOW
    assert (outcome, reason) == ("knowledge_gap", "grounding_reject")
    assert trace["answer_quality"]["relevance_reason"] == "wrong_action"


async def test_cited_cta_cannot_count_as_resolved_specialist_request(migrated_db, monkeypatch):
    provider = RecordedProvider(
        request("specialist appointment contact", relation="correction", intent="appointment"),
        CTA,
        CTA,
        {"status": "reject", "reason": "no_actionable_route"},
    )
    body, outcome, reason, _, _ = await run_chat(
        monkeypatch, provider, "i meant with specialist", history=True
    )
    assert body != CTA
    assert (outcome, reason) == ("knowledge_gap", "grounding_reject")


async def test_no_evidence_produces_precise_limitation_instead_of_scope_redirect(
    migrated_db, monkeypatch
):
    answer = "I cannot confirm the employer account enrollment steps."
    provider = RecordedProvider(
        request("employer account enrollment", intent="account_setup"),
        answer,
        None,
        {"status": "unsupported_detail", "reason": "responsive"},
    )
    body, outcome, reason, _, _ = await run_chat(
        monkeypatch, provider, "How do I open an employer account?", with_evidence=False
    )
    assert body == answer
    assert (outcome, reason) == ("knowledge_gap", "needs_confirmation")


async def test_explicit_contextual_transfer_changes_real_state(migrated_db, monkeypatch):
    provider = RecordedProvider(
        request(
            "connect to a specialist in this chat now", relation="continuation", intent="handoff"
        ),
        "",
        None,
        None,
    )
    _, _, _, state, _ = await run_chat(
        monkeypatch, provider, "Please bring one into this chat now", history=True
    )
    assert state == "queued"
    assert len(provider.calls) == 1


@pytest.mark.parametrize("relation", ["standalone", "topic_change"])
async def test_collection_appointment_question_still_accepts_candidate_workflow(
    migrated_db, monkeypatch, relation
):
    provider = RecordedProvider(
        request("candidate collection appointment", relation=relation, intent="appointment"),
        WORKFLOW,
        WORKFLOW,
        {"status": "answered", "reason": "responsive"},
    )
    body, outcome, _, state, trace = await run_chat(
        monkeypatch,
        provider,
        "Does the candidate need an appointment at the collection site?",
        history=relation == "topic_change",
    )
    assert body == WORKFLOW
    assert (outcome, state) == ("synthesized_answer", "bot")
    assert trace["retrieval"]["carried_evidence_ids"] == []


async def test_public_contact_without_provider_attribution_is_verified_and_persisted(
    migrated_db, monkeypatch
):
    provider = RecordedProvider(
        request("specialist pricing contact", intent="contact"),
        CONTACT,
        None,
        {"status": "answered", "reason": "responsive"},
    )
    body, outcome, _, _, trace = await run_chat(
        monkeypatch, provider, "What is the specialist email?"
    )
    assert body == CONTACT
    assert outcome == "synthesized_answer"
    assert trace["contact_attribution"]["attached"] == 1
    assert trace["persisted_citation_count"] == 1


async def test_unknown_contact_is_not_attributed_or_released(migrated_db, monkeypatch):
    unverified = "Email bookings@invented.test to book an appointment."
    provider = RecordedProvider(
        request("specialist appointment contact", intent="contact"),
        unverified,
        None,
        {"status": "answered", "reason": "responsive"},
    )
    body, outcome, reason, _, trace = await run_chat(
        monkeypatch, provider, "How can I contact sales?"
    )
    assert body != unverified
    assert (outcome, reason) == ("knowledge_gap", "grounding_reject")
    assert trace["persisted_citation_count"] == 0


@pytest.mark.parametrize(
    "answer",
    [
        "I have not booked an appointment.",
        "I have not booked an appointment for you.",
        "No he reservado ninguna cita.",
        "No he reservado ninguna cita para usted.",
    ],
)
async def test_chat_action_status_does_not_need_a_company_citation(
    migrated_db, monkeypatch, answer
):
    provider = RecordedProvider(
        request("has this chat booked the specialist appointment", intent="appointment"),
        answer,
        None,
        {"status": "answered", "reason": "responsive"},
    )
    body, outcome, _, _, trace = await run_chat(
        monkeypatch, provider, "Have you booked the appointment?", history=True
    )
    assert body == answer
    assert outcome == "synthesized_answer"
    assert trace["persisted_citation_count"] == 0
    assert trace["persisted_fallback_count"] == 0


@pytest.mark.parametrize(
    ("answer", "accepted"),
    [
        (
            "Contact inquiries@sample-site.example.com for a quote, but I cannot confirm whether rates are guaranteed for a year.",
            True,
        ),
        (
            "Contact inquiries@sample-site.example.com to ask about an annual rate guarantee.",
            True,
        ),
        ("Contact inquiries@sample-site.example.com for a guaranteed annual rate.", False),
    ],
)
async def test_guarantee_questions_are_distinguished_from_promises_in_persisted_replies(
    migrated_db, monkeypatch, answer, accepted
):
    provider = RecordedProvider(
        request("annual pricing guarantee contact", intent="information"),
        answer,
        CONTACT,
        {"status": "supported_next_step", "reason": "responsive"},
    )
    body, outcome, reason, _, trace = await run_chat(
        monkeypatch, provider, "Can you guarantee the price for a year?", history=True
    )
    if accepted:
        assert body == answer
        assert (outcome, reason) == ("partial_answer", "supported_next_step")
        assert trace["persisted_citation_count"] > 0
    else:
        assert body != answer
        assert (outcome, reason) == ("knowledge_gap", "grounding_reject")
        assert trace["persisted_citation_count"] == 0


async def test_semantic_edit_removes_unsupported_sentence_and_preserves_real_citations(
    migrated_db, monkeypatch
):
    unsupported = "Your discount depends on account details and location."
    limitation = "I cannot confirm the discount percentage."
    provider = RecordedProvider(
        request("drug test discount percentage", intent="information"),
        f"{CONTACT} {unsupported} {limitation}",
        CONTACT,
        [
            {
                "status": "reject",
                "reason": "unsupported_claim",
                "remove_sentences": [unsupported],
            },
            {"status": "supported_next_step", "reason": "responsive"},
        ],
    )
    body, outcome, reason, _, trace = await run_chat(
        monkeypatch, provider, "What percentage discount do we get?", prior_misses=1
    )
    assert body == f"{CONTACT} {limitation}"
    assert (outcome, reason) == ("partial_answer", "supported_next_step")
    assert trace["relevance_edit"]["removed"] == [unsupported]
    assert trace["persisted_citation_count"] > 0
    assert trace["persisted_fallback_count"] == 0
    # Resolution, one draft, assessment, then reassessment. No rewrite call.
    assert len(provider.calls) == 4


async def test_unknown_detail_contact_omits_sales_copy_and_inferred_rate_conditions(
    migrated_db, monkeypatch
):
    limitation = "I cannot confirm the discount percentage."
    provider = RecordedProvider(
        request("drug test discount percentage", intent="information"),
        f"{limitation} Discounts depend on account details. {CONTACT}",
        CONTACT,
        {"status": "supported_next_step", "reason": "responsive"},
    )
    body, outcome, reason, _, trace = await run_chat(
        monkeypatch, provider, "What percentage discount do we get?"
    )
    assert body == f"{limitation}\n\nYou can contact us at inquiries@sample-site.example.com."
    assert (outcome, reason) == ("partial_answer", "supported_next_step")
    assert trace["unknown_contact"]["condensed"]
    assert trace["persisted_citation_count"] == 1
    assert len(provider.calls) == 3
