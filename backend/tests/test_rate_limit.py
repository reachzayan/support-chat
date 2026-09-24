import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import session_maker
from app.services.conversation_service import CommandError, ConversationService
from tests.bot_fixtures import insert_bot_conversation
from tests.bot_fixtures import insert_site as insert_site_async
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_PASSWORD,
    DEMO_PUBLIC_KEY,
    DEMO_SITE_KEY,
    HOST_ORIGIN,
    insert_site,
    insert_staff,
    message_count,
    post_bootstrap,
    visitor_count,
)


def _set_budgets(monkeypatch, **values: str) -> None:
    from app.settings import reset_settings_cache

    for key, value in values.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()


def test_third_new_visitor_is_429_and_creates_zero_rows(client: TestClient, monkeypatch) -> None:
    insert_site(DEMO_SITE_KEY, "Demo", DEMO_PUBLIC_KEY)
    _set_budgets(monkeypatch, RATE_VISITOR_CREATE="2")
    first = post_bootstrap(client)
    second = post_bootstrap(client)
    third = post_bootstrap(client)
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert visitor_count() == 2


def test_idempotent_bootstrap_does_not_spend_create_budget(client: TestClient, monkeypatch) -> None:
    insert_site(DEMO_SITE_KEY, "Demo", DEMO_PUBLIC_KEY)
    _set_budgets(monkeypatch, RATE_VISITOR_CREATE="1")
    first = post_bootstrap(client)
    resume = first.json()["resume_token"]
    replay = post_bootstrap(
        client,
        {"site_key": DEMO_SITE_KEY, "public_key": DEMO_PUBLIC_KEY, "resume_token": resume},
    )
    assert first.status_code == 200
    assert replay.status_code == 200
    assert visitor_count() == 1


async def test_third_new_visitor_message_adds_zero_rows(migrated_db, monkeypatch) -> None:
    _set_budgets(monkeypatch, RATE_VISITOR_SUBMIT="2")
    async with session_maker()() as session:
        site = await insert_site_async(session, "samplesite", "SampleSite")
        visitor, conversation = await insert_bot_conversation(session, site)
        conversation.state = "queued"
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id
        site_id = site.id

    async def send(client_id: str, body: str) -> None:
        async with session_maker()() as session:
            await ConversationService(session).visitor_message(
                conversation_id,
                visitor_id,
                HOST_ORIGIN,
                uuid.UUID(client_id),
                body,
            )

    await send("10000000-0000-4000-8000-000000000001", "first")
    await send("10000000-0000-4000-8000-000000000002", "second")
    assert message_count(conversation_id, role="visitor") == 2
    try:
        await send("10000000-0000-4000-8000-000000000003", "third")
        raise AssertionError("third submission should be rate limited")
    except CommandError as exc:
        assert exc.code == "rate_limited"
    assert message_count(conversation_id, role="visitor") == 2
    assert visitor_count(site_id) == 1


def test_third_login_failure_is_429_and_does_not_issue_cookies(
    client: TestClient, monkeypatch
) -> None:
    insert_staff(ALEX_EMAIL, "Alex Morgan", ALEX_PASSWORD)
    _set_budgets(monkeypatch, RATE_LOGIN_FAILURE="2")
    payload = {"email": ALEX_EMAIL, "password": "wrong-password"}
    assert client.post("/auth/login", json=payload).status_code == 401
    assert client.post("/auth/login", json=payload).status_code == 401
    third = client.post("/auth/login", json=payload)
    assert third.status_code == 429
    assert "supportchat_refresh=" not in " ".join(third.headers.get_list("set-cookie")).lower()


def test_bootstrap_fails_closed_when_limiter_is_down(client: TestClient, monkeypatch) -> None:
    insert_site(DEMO_SITE_KEY, "Demo", DEMO_PUBLIC_KEY)

    def boom(*_args, **_kwargs):
        raise RuntimeError("redis down")

    monkeypatch.setattr("app.services.rate_limit.get_redis", boom)
    response = post_bootstrap(client)
    assert response.status_code == 503
    assert visitor_count() == 0


def test_login_fails_closed_when_limiter_is_down(client: TestClient, monkeypatch) -> None:
    insert_staff(ALEX_EMAIL, "Alex Morgan", ALEX_PASSWORD)

    def boom(*_args, **_kwargs):
        raise RuntimeError("redis down")

    monkeypatch.setattr("app.services.rate_limit.get_redis", boom)
    response = client.post("/auth/login", json={"email": ALEX_EMAIL, "password": ALEX_PASSWORD})
    assert response.status_code == 503
    assert "supportchat_refresh=" not in " ".join(response.headers.get_list("set-cookie")).lower()


async def test_visitor_message_fails_closed_when_limiter_is_down(migrated_db, monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("redis down")

    monkeypatch.setattr("app.services.rate_limit.get_redis", boom)
    async with session_maker()() as session:
        site = await insert_site_async(session, "samplesite", "SampleSite")
        visitor, conversation = await insert_bot_conversation(session, site)
        conversation.state = "queued"
        await session.commit()
        conversation_id = conversation.id
        visitor_id = visitor.id

    with pytest.raises(CommandError) as caught:
        async with session_maker()() as session:
            await ConversationService(session).visitor_message(
                conversation_id,
                visitor_id,
                HOST_ORIGIN,
                uuid.UUID("10000000-0000-4000-8000-000000000001"),
                "first",
            )
    assert caught.value.code == "unavailable"
    assert message_count(conversation_id, role="visitor") == 0


async def test_bootstrap_rate_key_hashes_site_key_and_sets_ttl(migrated_db) -> None:
    from app.redis import get_redis
    from app.services.rate_limit import RateLimiter

    site_key = "samplesite-attacker-controlled-key"
    await RateLimiter().hit_bootstrap("203.0.113.40", site_key)
    keys = await get_redis().keys("rate:bootstrap:*")
    assert keys
    assert all(site_key not in key for key in keys)
    ttl = await get_redis().ttl(keys[0])
    assert ttl > 0


async def test_login_budget_admission_is_atomic_under_concurrency(migrated_db, monkeypatch) -> None:
    from app.services.rate_limit import RateLimiter, RateLimitExceeded

    _set_budgets(monkeypatch, RATE_LOGIN_FAILURE="2")
    limiter = RateLimiter()

    async def reserve() -> str:
        try:
            await limiter.reserve_login("parallel@example.com", "203.0.113.9")
        except RateLimitExceeded:
            return "rejected"
        return "admitted"

    outcomes = await asyncio.gather(*(reserve() for _ in range(8)))
    assert outcomes.count("admitted") == 2
    assert outcomes.count("rejected") == 6


async def test_successful_login_releases_reserved_failure_budget(migrated_db, monkeypatch) -> None:
    from app.services.rate_limit import RateLimiter

    _set_budgets(monkeypatch, RATE_LOGIN_FAILURE="1")
    limiter = RateLimiter()
    await limiter.reserve_login("success@example.com", "203.0.113.10")
    await limiter.release_login("success@example.com", "203.0.113.10")
    await limiter.reserve_login("success@example.com", "203.0.113.10")
