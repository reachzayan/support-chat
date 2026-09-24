from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db import session_maker
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.handoff_repo import HandoffRepository
from tests.bot_fixtures import insert_bot_conversation, insert_site


async def test_expired_bot_generation_is_claimed_once_for_recovery(migrated_db) -> None:
    generation_id = uuid4()
    async with session_maker()() as session:
        site = await insert_site(session, "durable-bot", "Durable Bot")
        _visitor, conversation = await insert_bot_conversation(session, site)
        conversation.active_generation_id = generation_id
        conversation.generation_created_at = datetime.now(UTC) - timedelta(minutes=5)
        conversation.generation_lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    async with session_maker()() as first_session:
        claim = getattr(ConversationRepository(first_session), "claim_recoverable_generation", None)
        assert callable(claim), "bot generation recovery must be durable"
        first = await claim(recovery_grace=timedelta(seconds=2), lease=timedelta(minutes=2))

    async with session_maker()() as second_session:
        claim = ConversationRepository(second_session).claim_recoverable_generation
        second = await claim(recovery_grace=timedelta(seconds=2), lease=timedelta(minutes=2))

    assert first == (conversation.id, generation_id)
    assert second is None


async def test_fresh_unclaimed_bot_generation_gets_a_websocket_grace_period(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "fresh-bot", "Fresh Bot")
        _visitor, conversation = await insert_bot_conversation(session, site)
        conversation.active_generation_id = uuid4()
        conversation.generation_created_at = datetime.now(UTC)
        conversation.generation_lease_expires_at = None
        await session.commit()

    async with session_maker()() as session:
        claim = getattr(ConversationRepository(session), "claim_recoverable_generation", None)
        assert callable(claim), "bot generation recovery must be durable"
        result = await claim(recovery_grace=timedelta(seconds=5), lease=timedelta(minutes=2))

    assert result is None


async def test_handoff_summary_job_is_persisted_and_claimed_once(migrated_db) -> None:
    async with session_maker()() as session:
        site = await insert_site(session, "durable-summary", "Durable Summary")
        _visitor, conversation = await insert_bot_conversation(session, site)
        handoff = await HandoffRepository(session).create(
            conversation_id=conversation.id,
            site_id=site.id,
            escalation_reason="visitor_request",
            original_question="Can a specialist help?",
            clarification_answer=None,
            candidate_unit_ids=[],
            rejection_reasons=[],
            provider_stage_timings={},
            provider_status="ok",
            promised_response_by=None,
            route="live_queue",
            snapshot_id=None,
        )
        await session.commit()
        handoff_id = handoff.id

    async with session_maker()() as first_session:
        claim = getattr(HandoffRepository(first_session), "claim_next_summary", None)
        assert callable(claim), "handoff summary work must survive process restarts"
        first = await claim(lease=timedelta(minutes=2))

    async with session_maker()() as second_session:
        claim = HandoffRepository(second_session).claim_next_summary
        second = await claim(lease=timedelta(minutes=2))

    assert first is not None and first.id == handoff_id
    assert first.summary_status == "running"
    assert first.summary_attempts == 1
    assert second is None
