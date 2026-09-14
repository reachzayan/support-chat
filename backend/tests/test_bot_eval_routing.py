from app.chat.outcome_copy import WAITING_LINE
from app.db import session_maker
from app.services.bot_eval import load_dataset, run_case
from app.services.kb_embedder import FakeEmbedder
from tests.bot_fixtures import RecordingResponder, seed_brand_articles
from tests.ws_helpers import HOST_ORIGIN


async def test_routing_evals_do_not_queue_off_topic_or_skip_specialist(migrated_db) -> None:
    _site_key, cases = load_dataset()
    routing = [item for item in cases if item.family.startswith("routing.")]
    assert [item.id for item in routing[:3]] == [
        "off_topic.sad",
        "off_topic.fuel",
        "off_topic.gender",
    ]
    responder = RecordingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        await session.commit()
        failed: list[str] = []
        for case in routing:
            _observed, verdict = await run_case(
                session,
                easy,
                case,
                parent_origin=HOST_ORIGIN,
                responder=responder,
                embedder=FakeEmbedder(),
            )
            if not verdict.passed:
                failed.append(f"{case.id}: {', '.join(verdict.failures)}")
        assert failed == []
        assert responder.calls == []


async def test_france_capital_is_off_topic_not_a_specialist_offer(migrated_db) -> None:
    from app.services.bot_eval import EvalCase

    case = EvalCase(
        id="off_topic.capital",
        family="routing.off_topic",
        turns=("what's the capital of France",),
        expected_state="bot",
        expected_reason="off_topic",
        must_contain=("screening and compliance",),
        must_not_contain=("A specialist will join", "transfer you"),
    )
    responder = RecordingResponder()
    async with session_maker()() as session:
        easy, _bg, _timing, _fcra = await seed_brand_articles(session)
        await session.commit()
        observed, verdict = await run_case(
            session,
            easy,
            case,
            parent_origin=HOST_ORIGIN,
            responder=responder,
            embedder=FakeEmbedder(),
        )
    assert "screening and compliance" in observed.body.casefold()
    assert observed.state == "bot"
    assert observed.body != WAITING_LINE
    assert observed.system_reason == "off_topic"
    assert verdict.passed is True
    assert responder.calls == []
