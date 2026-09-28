from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.db import session_maker
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.services.full_context import load_live_units
from app.services.kb_embedder import FakeEmbedder
from app.services.kb_source_admin import KbSourceService
from app.services.site_admin import AdminError
from tests.bot_fixtures import insert_chunk, insert_site


async def test_page_toggle_preserves_individual_chunk_choices_and_cache_eligibility(
    migrated_db,
) -> None:
    """Catches a page toggle overwriting a disabled block or leaving cached blocks available."""
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        enabled_chunk = await insert_chunk(
            session,
            site,
            "Turnaround time",
            "Most negative results are reported within 24-48 hours.",
        )
        page = await session.get(KbPage, enabled_chunk.page_id)
        assert page is not None
        disabled_chunk = KbChunk(
            page_id=page.id,
            site_id=site.id,
            snapshot_id=enabled_chunk.snapshot_id,
            ordinal=1,
            kind="prose",
            heading="Privacy notice",
            answer_verbatim="Please review the privacy notice.",
            body="Please review the privacy notice.",
            enabled=False,
        )
        session.add(disabled_chunk)
        await session.commit()

        warmed = await load_live_units(session, [enabled_chunk.snapshot_id])
        assert [unit.answer_verbatim for unit in warmed] == [
            "Most negative results are reported within 24-48 hours."
        ]

        service = KbSourceService(session)
        await service.patch_page(page.id, enabled=False)
        disabled_page_units = await load_live_units(session, [enabled_chunk.snapshot_id])
        assert disabled_page_units == []

        await service.patch_page(page.id, enabled=True)
        await session.refresh(enabled_chunk)
        await session.refresh(disabled_chunk)
        restored = await load_live_units(session, [enabled_chunk.snapshot_id])
        assert enabled_chunk.enabled is True
        assert disabled_chunk.enabled is False
        assert [unit.answer_verbatim for unit in restored] == [
            "Most negative results are reported within 24-48 hours."
        ]


async def test_chunk_toggle_requires_live_snapshot_and_changes_retrievable_blocks(
    migrated_db,
) -> None:
    """Catches a disabled live chunk still reaching full-context prompts."""
    async with session_maker()() as session:
        site = await insert_site(session, "backgroundchecks", "Sample Services")
        chunk = await insert_chunk(
            session,
            site,
            "FCRA package",
            "FCRA-compliant employment screening.",
        )
        await session.commit()

        changed = await KbSourceService(session).patch_chunk(chunk.id, enabled=False)
        assert changed.enabled is False
        available = await load_live_units(session, [chunk.snapshot_id])
        assert available == []
        stored = await session.scalar(select(KbChunk).where(KbChunk.id == chunk.id))
        assert stored is not None
        assert stored.enabled is False


EDITED_BODY = "FCRA-compliant employment screening packages include county searches."
ORIGINAL_BODY = "Most negative results are reported within 24-48 hours."


async def test_chunk_body_edit_replaces_the_live_answer_text(migrated_db, monkeypatch) -> None:
    """Catches a body patch that leaves prompts answering from the old verbatim copy."""
    monkeypatch.setattr("app.services.kb_source_admin.default_embedder", lambda: FakeEmbedder())
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        chunk = await insert_chunk(session, site, "Turnaround time", ORIGINAL_BODY)
        await session.commit()
        edit_id = uuid4()

        saved = await KbSourceService(session).patch_chunk(
            chunk.id, body=EDITED_BODY, edit_id=edit_id
        )
        assert saved.body == EDITED_BODY
        units = await load_live_units(session, [chunk.snapshot_id])
        assert [unit.answer_verbatim for unit in units] == [EDITED_BODY]
        stored = await session.scalar(select(KbChunk).where(KbChunk.id == chunk.id))
        assert stored is not None
        assert stored.answer_verbatim == EDITED_BODY
        assert stored.embedding is not None
        assert stored.embedding[1] == pytest.approx(1.0)
        assert stored.embedding[0] == pytest.approx(0.0)
        found = await session.scalar(
            text(
                "SELECT id FROM kb_chunks "
                "WHERE id = :id AND search_document @@ plainto_tsquery('english', :q)"
            ),
            {"id": chunk.id, "q": "fcra"},
        )
        assert found == chunk.id


async def test_chunk_body_edit_replay_keeps_the_first_saved_text(migrated_db) -> None:
    """Catches a retried edit_id applying a different body or concatenating the first save."""
    async with session_maker()() as session:
        site = await insert_site(session, "backgroundchecks", "Sample Services")
        chunk = await insert_chunk(session, site, "Turnaround time", ORIGINAL_BODY)
        await session.commit()
        edit_id = uuid4()
        service = KbSourceService(session)

        first = await service.patch_chunk(chunk.id, body=EDITED_BODY, edit_id=edit_id)
        replay = await service.patch_chunk(chunk.id, body=EDITED_BODY, edit_id=edit_id)
        assert first.body == EDITED_BODY
        assert replay.body == EDITED_BODY

        with pytest.raises(AdminError, match="conflict"):
            await service.patch_chunk(
                chunk.id,
                body="Something else a specialist never saved.",
                edit_id=edit_id,
            )
        stored = await session.scalar(select(KbChunk).where(KbChunk.id == chunk.id))
        assert stored is not None
        assert stored.body == EDITED_BODY
        assert stored.answer_verbatim == EDITED_BODY


async def test_chunk_body_edit_rejects_blank_text(migrated_db) -> None:
    """Catches a whitespace-only save wiping a retrieved answer."""
    async with session_maker()() as session:
        site = await insert_site(session, "samplesite", "SampleSite")
        chunk = await insert_chunk(session, site, "Turnaround time", ORIGINAL_BODY)
        await session.commit()

        with pytest.raises(AdminError, match="invalid"):
            await KbSourceService(session).patch_chunk(chunk.id, body="   ", edit_id=uuid4())
        stored = await session.scalar(select(KbChunk).where(KbChunk.id == chunk.id))
        assert stored is not None
        assert stored.body == ORIGINAL_BODY
