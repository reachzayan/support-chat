import hashlib
import uuid

from app.chat.outcome_copy import (
    DISENGAGE_LINE,
    KEEP_HELPING_LINE,
    POLICY_BOUNDARY,
    TRANSFER_OFFER,
    WAITING_LINE,
)
from app.db import session_maker
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.services.conversation_service import ConversationService
from app.services.kb_embedder import FakeEmbedder, configured_embedder_id
from tests.bot_fixtures import (
    RecordingResponder,
    insert_bot_conversation,
    seed_brand_articles,
)
from tests.ws_helpers import HOST_ORIGIN, conversation_state, message_count

OFF_TOPIC = "I can't help with that here."
DOT_YES = (
    "Yes. We support employers with DOT drug and alcohol testing, random pool management, "
    "MIS reporting, and DOT physicals, all performed in line with 49 CFR Part 40 requirements."
)
SERVICES_BODY = (
    "Pre-employment drug screens, random testing programs, occupational health services, "
    "and sample services."
)


async def _turn(session, site, body: str, responder=None):
    visitor, conversation = await insert_bot_conversation(session, site)
    await session.commit()
    service = ConversationService(
        session,
        responder=responder or RecordingResponder(),
        embedder=FakeEmbedder(),
    )
    result = await service.visitor_message(
        conversation.id, visitor.id, HOST_ORIGIN, uuid.uuid4(), body
    )
    if result.generation_id is not None:
        await service.run_bot_turn(conversation.id, result.generation_id)
    return conversation.id, service


def _assert_stays_bot_without_handoff(conversation_id: uuid.UUID) -> None:
    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=OFF_TOPIC) == 1
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0
    assert message_count(conversation_id, role="system", body=TRANSFER_OFFER) == 0
    assert message_count(conversation_id, role="system", body=POLICY_BOUNDARY) == 0
    assert message_count(conversation_id, role="system", body=DISENGAGE_LINE) == 0
    assert message_count(conversation_id, role="bot") == 0


async def test_sad_message_stays_with_bot_and_does_not_queue(migrated_db) -> None:
    responder = RecordingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id, _service = await _turn(session, easy, "I am sad", responder)

    _assert_stays_bot_without_handoff(conversation_id)
    assert responder.calls == []


async def test_fuel_prices_stay_with_bot_and_do_not_queue(migrated_db) -> None:
    responder = RecordingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id, _service = await _turn(session, easy, "What's the fuel prices", responder)

    _assert_stays_bot_without_handoff(conversation_id)
    assert responder.calls == []


async def test_gender_question_stays_with_bot_and_does_not_queue(migrated_db) -> None:
    responder = RecordingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id, _service = await _turn(session, easy, "are you a male", responder)

    _assert_stays_bot_without_handoff(conversation_id)
    assert responder.calls == []


async def test_specialist_request_stays_with_bot_instead_of_queueing(migrated_db) -> None:
    responder = RecordingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        conversation_id, _service = await _turn(
            session, easy, "I want to talk to a specialist", responder
        )

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="system", body=KEEP_HELPING_LINE) == 1
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0
    assert message_count(conversation_id, role="system", body=OFF_TOPIC) == 0
    assert responder.calls == []


async def _insert_faq(session, site, question: str, answer: str, *, kind: str = "faq") -> KbChunk:
    url = f"https://sample-site.example.com/faq#{hashlib.sha256(question.encode()).hexdigest()[:8]}"
    source = KbSource(
        site_id=site.id,
        start_url=url,
        mode="list",
        seed_urls=[url],
        status="ready",
        page_count=1,
        embedder_id=configured_embedder_id(),
        enabled=True,
    )
    session.add(source)
    await session.flush()
    page = KbPage(
        source_id=source.id,
        site_id=site.id,
        url=url,
        title=question,
        content_text=answer,
        content_sha256=hashlib.sha256(answer.encode()).hexdigest(),
        http_status=200,
        enabled=True,
    )
    session.add(page)
    await session.flush()
    snapshot = KbSnapshot(
        site_id=site.id,
        source_id=source.id,
        state="live",
        content_hash=hashlib.sha256(answer.encode()).hexdigest(),
        token_estimate=40,
    )
    session.add(snapshot)
    await session.flush()
    vectors = await FakeEmbedder().embed_documents([f"{question}\n{answer}"])
    chunk = KbChunk(
        page_id=page.id,
        site_id=site.id,
        snapshot_id=snapshot.id,
        ordinal=0,
        kind=kind,
        heading=question,
        canonical_question=question if kind == "faq" else None,
        answer_verbatim=answer,
        aliases=[],
        body=answer,
        embedding=vectors[0],
        approved=True,
        enabled=True,
    )
    session.add(chunk)
    await session.flush()
    return chunk


async def test_background_section_is_answered_verbatim_without_the_model(migrated_db) -> None:
    responder = RecordingResponder()
    body = "Complete your hiring by bundling background screening with drug testing."
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        await _insert_faq(
            session,
            easy,
            "Sample Services",
            body,
            kind="section",
        )
        await session.commit()
        conversation_id, _service = await _turn(
            session, easy, "do you do sample services", responder
        )

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, role="bot", body=body) == 1
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0
    assert responder.calls == []


async def test_services_overview_does_not_paste_dot_yes_faq(migrated_db) -> None:
    responder = RecordingResponder(answer=SERVICES_BODY)
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        await _insert_faq(
            session,
            easy,
            "Do you provide DOT-compliant drug and alcohol testing?",
            DOT_YES,
        )
        await _insert_faq(
            session,
            easy,
            "What services do you offer?",
            SERVICES_BODY,
        )
        await session.commit()
        conversation_id, _service = await _turn(
            session, easy, "what services do you offer?", responder
        )

    assert conversation_state(conversation_id) == "bot"
    assert message_count(conversation_id, body=DOT_YES) == 0
    assert message_count(conversation_id, role="system", body=WAITING_LINE) == 0


async def test_overview_query_does_not_prefer_a_single_faq_unit(migrated_db) -> None:
    from app.services.full_context import likeliest_unit_id

    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        dot = await _insert_faq(
            session,
            easy,
            "Do you provide DOT-compliant drug and alcohol testing?",
            DOT_YES,
        )
        await session.commit()
        preferred = await likeliest_unit_id(
            session,
            easy.id,
            [dot.snapshot_id],
            "what services do you offer?",
        )
    assert preferred is None


async def test_cost_query_does_not_fastpath_preemployment_blurb(migrated_db) -> None:
    from app.services.faq_fastpath import normalize_fast_query, try_fast_answer

    hire_body = "Streamlined, compliant testing for new hires so HR can move fast."
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        section = await _insert_faq(
            session,
            easy,
            "Pre-Employment Drug Screens",
            hire_body,
            kind="section",
        )
        await session.commit()
        normalized = normalize_fast_query("how much does a drug screen cost")
        hit = await try_fast_answer(session, easy.id, [section.snapshot_id], normalized)
    assert hit is None or "new hires" not in hit.answer_verbatim.casefold()


async def test_clinic_query_skips_marketing_cta_and_uses_network_faq(migrated_db) -> None:
    from app.services.faq_fastpath import normalize_fast_query, try_fast_answer

    cta = (
        "No more chasing clinics, waiting for results, or compliance surprises. "
        "Talk to a specialist or jump into the portal."
    )
    network = (
        "Yes. The SampleLab collection-site network covers thousands of clinics nationwide "
        "with electronic scheduling and reporting."
    )
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        cta_chunk = await _insert_faq(
            session, easy, "Return your peace of mind.", cta, kind="section"
        )
        faq = await _insert_faq(
            session,
            easy,
            "Do you support multi-location or nationwide employers?",
            network,
        )
        await session.commit()
        hit = await try_fast_answer(
            session,
            easy.id,
            [cta_chunk.snapshot_id, faq.snapshot_id],
            normalize_fast_query("where are your clinics"),
        )
    assert hit is not None
    assert hit.answer_verbatim == network
    assert "talk to a specialist" not in hit.answer_verbatim.casefold()
