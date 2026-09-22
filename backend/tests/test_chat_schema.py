import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models.article import KbArticle
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.site import Site
from app.models.visitor import Visitor
from tests.conftest import TEST_DATABASE_URL

SYNC_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def _session() -> Session:
    engine = create_engine(SYNC_URL)
    return sessionmaker(engine, expire_on_commit=False)()


def _site(session: Session, key: str, name: str) -> Site:
    site = Site(
        key=key,
        name=name,
        public_key=uuid.uuid4().hex + uuid.uuid4().hex,
        allowed_origins=["http://localhost:3000"],
        greeting="We're away at the moment.",
        privacy_url="http://localhost:3000/privacy",
    )
    session.add(site)
    session.flush()
    return site


def test_same_resume_hash_is_isolated_per_site(client) -> None:
    session = _session()
    try:
        easy = _site(session, "samplesite", "SampleSite")
        bg = _site(session, "backgroundchecks", "Sample Services")
        token_hash = "abc123hash"
        session.add_all(
            [
                Visitor(site_id=easy.id, resume_token_hash=token_hash),
                Visitor(site_id=bg.id, resume_token_hash=token_hash),
            ]
        )
        session.commit()
        easy_found = session.scalars(
            select(Visitor).where(
                Visitor.site_id == easy.id, Visitor.resume_token_hash == token_hash
            )
        ).one()
        bg_found = session.scalars(
            select(Visitor).where(Visitor.site_id == bg.id, Visitor.resume_token_hash == token_hash)
        ).one()
        assert easy_found.id != bg_found.id
        assert easy_found.site_id == easy.id
        assert bg_found.site_id == bg.id
    finally:
        session.close()


def test_cross_site_visitor_pairing_fails(client) -> None:
    session = _session()
    try:
        easy = _site(session, "samplesite", "SampleSite")
        bg = _site(session, "backgroundchecks", "Sample Services")
        visitor = Visitor(site_id=easy.id, resume_token_hash="hash-a")
        session.add(visitor)
        session.flush()
        session.add(Conversation(site_id=bg.id, visitor_id=visitor.id, state="prechat"))
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_one_open_conversation_per_visitor(client) -> None:
    session = _session()
    try:
        site = _site(session, "demo", "Demo")
        visitor = Visitor(site_id=site.id, resume_token_hash="open-hash")
        session.add(visitor)
        session.commit()

        def _insert() -> None:
            local = _session()
            try:
                local.add(Conversation(site_id=site.id, visitor_id=visitor.id, state="prechat"))
                local.commit()
            finally:
                local.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                future.exception() for future in [pool.submit(_insert), pool.submit(_insert)]
            ]
        assert sum(err is None for err in results) == 1
        assert sum(isinstance(err, IntegrityError) for err in results) == 1
        open_rows = session.scalars(
            select(Conversation).where(
                Conversation.visitor_id == visitor.id,
                Conversation.state != "closed",
            )
        ).all()
        assert len(open_rows) == 1
    finally:
        session.close()


def test_duplicate_client_message_id_is_stable(client) -> None:
    session = _session()
    try:
        site = _site(session, "demo", "Demo")
        visitor = Visitor(site_id=site.id, resume_token_hash="msg-hash")
        session.add(visitor)
        session.flush()
        convo = Conversation(site_id=site.id, visitor_id=visitor.id, state="bot")
        session.add(convo)
        session.flush()
        client_id = uuid.uuid4()
        first = Message(
            conversation_id=convo.id,
            client_message_id=client_id,
            role="visitor",
            body="How fast are DOT results?",
        )
        session.add(first)
        session.commit()
        canonical = first.id
        session.add(
            Message(
                conversation_id=convo.id,
                client_message_id=client_id,
                role="visitor",
                body="How fast are DOT results?",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        rows = session.scalars(select(Message).where(Message.conversation_id == convo.id)).all()
        assert len(rows) == 1
        assert rows[0].id == canonical
        assert rows[0].body == "How fast are DOT results?"
    finally:
        session.close()


def test_message_role_constraints(client) -> None:
    session = _session()
    try:
        site = _site(session, "demo", "Demo")
        visitor = Visitor(site_id=site.id, resume_token_hash="role-hash")
        session.add(visitor)
        session.flush()
        convo = Conversation(site_id=site.id, visitor_id=visitor.id, state="bot")
        session.add(convo)
        session.flush()
        article_id = uuid.uuid4()

        session.add(
            Message(
                conversation_id=convo.id,
                site_id=site.id,
                client_message_id=uuid.uuid4(),
                role="visitor",
                body="hi",
                source_article_ids=[article_id],
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            Message(
                conversation_id=convo.id,
                site_id=site.id,
                role="agent",
                body="I can help with that.",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            Message(
                conversation_id=convo.id,
                site_id=site.id,
                client_message_id=uuid.uuid4(),
                role="visitor",
                body="hi",
                author_user_id=uuid.uuid4(),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            Message(
                conversation_id=convo.id,
                site_id=site.id,
                role="bot",
                body="Most negative results are reported within 24-48 hours.",
                source_article_ids=[],
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_disabling_article_drops_it_from_enabled_search(client) -> None:
    session = _session()
    try:
        site = _site(session, "samplesite", "SampleSite")
        visitor = Visitor(site_id=site.id, resume_token_hash="kb-hash")
        session.add(visitor)
        session.flush()
        article = KbArticle(
            site_id=site.id,
            title="How quickly are results available?",
            body="Most negative results are reported within 24-48 hours.",
            enabled=True,
        )
        session.add(article)
        session.flush()
        convo = Conversation(site_id=site.id, visitor_id=visitor.id, state="bot")
        session.add(convo)
        session.flush()
        bot_row = Message(
            conversation_id=convo.id,
            role="bot",
            body="Most negative results are reported within 24-48 hours.",
            source_article_ids=[article.id],
        )
        session.add(bot_row)
        session.commit()
        enabled_ids = session.scalars(
            select(KbArticle.id).where(KbArticle.site_id == site.id, KbArticle.enabled.is_(True))
        ).all()
        assert article.id in enabled_ids
        article.enabled = False
        session.commit()
        enabled_ids = session.scalars(
            select(KbArticle.id).where(KbArticle.site_id == site.id, KbArticle.enabled.is_(True))
        ).all()
        assert article.id not in enabled_ids
        historical = session.get(Message, bot_row.id)
        assert historical is not None
        assert list(historical.source_article_ids) == [article.id]
        assert historical.body == "Most negative results are reported within 24-48 hours."
    finally:
        session.close()


def test_origin_canonicalization_rejects_unsafe_values() -> None:
    from app.repositories.origins import InvalidOrigin, canonicalize_origin, canonicalize_origins

    assert canonicalize_origin("https://Example.COM:443") == "https://example.com"
    assert canonicalize_origin("http://localhost:3000") == "http://localhost:3000"
    with pytest.raises(InvalidOrigin):
        canonicalize_origin("https://*.example.com")
    with pytest.raises(InvalidOrigin):
        canonicalize_origin("https://user:pass@example.com")
    with pytest.raises(InvalidOrigin):
        canonicalize_origin("https://example.com/path")
    with pytest.raises(InvalidOrigin):
        canonicalize_origin("https://example.com?q=1")
    with pytest.raises(InvalidOrigin):
        canonicalize_origin("https://example.com#frag")
    with pytest.raises(InvalidOrigin):
        canonicalize_origin("ftp://example.com")
    with pytest.raises(InvalidOrigin, match="invalid port"):
        canonicalize_origin("https://example.com:abc")
    assert canonicalize_origins(["http://localhost:3000", "http://localhost:3000"]) == [
        "http://localhost:3000"
    ]
