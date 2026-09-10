import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.site import Site
from tests.conftest import TEST_DATABASE_URL

SYNC_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")
TIMING_BODY = "Most negative results are reported within 24-48 hours."
FCRA_BODY = "The Fair Credit Reporting Act governs employment sample services."


def _session() -> Session:
    engine = create_engine(SYNC_URL)
    return sessionmaker(engine, expire_on_commit=False)()


def _site(session: Session, key: str, name: str) -> Site:
    site = Site(
        key=key,
        name=name,
        public_key=uuid.uuid4().hex + uuid.uuid4().hex,
        allowed_origins=["https://sample-site.example.com"],
        greeting="We're away at the moment.",
        privacy_url="http://localhost:3000/privacy",
    )
    session.add(site)
    session.flush()
    return site


def _source(session: Session, site: Site, start_url: str) -> KbSource:
    source = KbSource(
        site_id=site.id,
        start_url=start_url,
        mode="list",
        seed_urls=[start_url],
        include_globs=[],
        exclude_globs=[],
        status="ready",
        embedder_id="openai:text-embedding-3-small:1536",
        enabled=True,
    )
    session.add(source)
    session.flush()
    return source


def _live_snapshot(session: Session, source: KbSource) -> KbSnapshot:
    snapshot = KbSnapshot(
        site_id=source.site_id,
        source_id=source.id,
        state="live",
        content_hash="a" * 64,
        token_estimate=0,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def test_chunk_search_is_isolated_to_site_id(client) -> None:
    session = _session()
    try:
        easy = _site(session, "samplesite", "SampleSite")
        bg = _site(session, "backgroundchecks", "Sample Services")
        easy_source = _source(session, easy, "https://sample-site.example.com/faq")
        bg_source = _source(session, bg, "https://sample-services.example.com/fcra")
        easy_page = KbPage(
            source_id=easy_source.id,
            site_id=easy.id,
            url="https://sample-site.example.com/faq",
            title="Turnaround",
            content_text=TIMING_BODY,
            content_sha256="a" * 64,
            http_status=200,
            enabled=True,
        )
        bg_page = KbPage(
            source_id=bg_source.id,
            site_id=bg.id,
            url="https://sample-services.example.com/fcra",
            title="FCRA",
            content_text=FCRA_BODY,
            content_sha256="b" * 64,
            http_status=200,
            enabled=True,
        )
        session.add_all([easy_page, bg_page])
        session.flush()
        easy_snap = _live_snapshot(session, easy_source)
        bg_snap = _live_snapshot(session, bg_source)
        easy_chunk = KbChunk(
            page_id=easy_page.id,
            site_id=easy.id,
            snapshot_id=easy_snap.id,
            ordinal=0,
            heading="Turnaround",
            body=TIMING_BODY,
            answer_verbatim=TIMING_BODY,
            enabled=True,
        )
        bg_chunk = KbChunk(
            page_id=bg_page.id,
            site_id=bg.id,
            snapshot_id=bg_snap.id,
            ordinal=0,
            heading="FCRA",
            body=FCRA_BODY,
            answer_verbatim=FCRA_BODY,
            enabled=True,
        )
        session.add_all([easy_chunk, bg_chunk])
        session.commit()
        easy_ids = session.scalars(select(KbChunk.id).where(KbChunk.site_id == easy.id)).all()
        bg_ids = session.scalars(select(KbChunk.id).where(KbChunk.site_id == bg.id)).all()
        assert easy_ids == [easy_chunk.id]
        assert bg_ids == [bg_chunk.id]
        assert TIMING_BODY in easy_chunk.body
        assert easy_chunk.id not in bg_ids
    finally:
        session.close()


def test_duplicate_source_url_on_same_site_is_rejected(client) -> None:
    session = _session()
    try:
        site = _site(session, "samplesite", "SampleSite")
        _source(session, site, "https://sample-site.example.com/faq")
        session.commit()
        session.add(
            KbSource(
                site_id=site.id,
                start_url="https://sample-site.example.com/faq",
                mode="list",
                seed_urls=["https://sample-site.example.com/faq"],
                include_globs=[],
                exclude_globs=[],
                status="queued",
                embedder_id="openai:text-embedding-3-small:1536",
                enabled=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_deleting_source_cascades_pages_and_chunks(client) -> None:
    session = _session()
    try:
        site = _site(session, "samplesite", "SampleSite")
        source = _source(session, site, "https://sample-site.example.com/faq")
        page = KbPage(
            source_id=source.id,
            site_id=site.id,
            url="https://sample-site.example.com/faq",
            title="Turnaround",
            content_text=TIMING_BODY,
            content_sha256="a" * 64,
            http_status=200,
            enabled=True,
        )
        session.add(page)
        session.flush()
        snapshot = _live_snapshot(session, source)
        session.add(
            KbChunk(
                page_id=page.id,
                site_id=site.id,
                snapshot_id=snapshot.id,
                ordinal=0,
                heading="Turnaround",
                body=TIMING_BODY,
                answer_verbatim=TIMING_BODY,
                enabled=True,
            )
        )
        session.commit()
        source_id = source.id
        session.delete(source)
        session.commit()
        pages = session.scalars(select(KbPage).where(KbPage.source_id == source_id)).all()
        chunks = session.scalars(select(KbChunk).where(KbChunk.site_id == site.id)).all()
        assert pages == []
        assert chunks == []
    finally:
        session.close()


def test_vector_extension_is_available(client) -> None:
    session = _session()
    try:
        exists = session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
        assert exists.scalar_one() == "vector"
    finally:
        session.close()


def test_chunk_search_document_weights_question_and_aliases_above_body(client) -> None:
    session = _session()
    try:
        site = _site(session, "samplesite", "SampleSite")
        source = _source(session, site, "https://sample-site.example.com/faq")
        snapshot = _live_snapshot(session, source)
        page = KbPage(
            source_id=source.id,
            site_id=site.id,
            url="https://sample-site.example.com/faq",
            title="Turnaround",
            content_text=TIMING_BODY,
            content_sha256="a" * 64,
            http_status=200,
            enabled=True,
        )
        session.add(page)
        session.flush()
        chunk = KbChunk(
            page_id=page.id,
            site_id=site.id,
            snapshot_id=snapshot.id,
            ordinal=0,
            kind="faq",
            heading="zyxheadingtoken",
            canonical_question="zyxquestiontoken",
            answer_verbatim=TIMING_BODY,
            aliases=["zyxaliastoken"],
            body="zyxbodytoken",
            enabled=True,
        )
        session.add(chunk)
        session.commit()
        session.refresh(chunk)
        weights = session.execute(
            text("SELECT search_document::text FROM kb_chunks WHERE id = :id"),
            {"id": chunk.id},
        ).scalar_one()
        assert "'zyxquestiontoken':1A" in weights
        assert "'zyxaliastoken':2A" in weights
        assert "'zyxheadingtoken':3B" in weights
        assert "'zyxbodytoken':4C" in weights
    finally:
        session.close()


def test_one_live_snapshot_per_source_and_site_id_must_match_source(client) -> None:
    session = _session()
    try:
        easy = _site(session, "samplesite", "SampleSite")
        bg = _site(session, "backgroundchecks", "Sample Services")
        source = _source(session, easy, "https://sample-site.example.com/faq")
        _live_snapshot(session, source)
        session.commit()
        session.add(
            KbSnapshot(
                site_id=easy.id,
                source_id=source.id,
                state="live",
                content_hash="b" * 64,
                token_estimate=0,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(
            KbSnapshot(
                site_id=bg.id,
                source_id=source.id,
                state="building",
                content_hash="c" * 64,
                token_estimate=0,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_messages_snapshot_id_column_exists(client) -> None:
    session = _session()
    try:
        exists = session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'messages' AND column_name = 'snapshot_id'"
            )
        ).scalar_one()
        assert exists == "snapshot_id"
    finally:
        session.close()


def test_human_enabled_requires_bot_enabled(client) -> None:
    session = _session()
    try:
        site = Site(
            key="samplesite",
            name="SampleSite",
            public_key=uuid.uuid4().hex + uuid.uuid4().hex,
            allowed_origins=["https://sample-site.example.com"],
            greeting="We're away at the moment.",
            privacy_url="http://localhost:3000/privacy",
            bot_enabled=False,
            human_enabled=True,
        )
        session.add(site)
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()
