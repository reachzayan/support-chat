"""Persist a grounded reply and lock its citations inside the caller's transaction."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.display_citations import visitor_citation_payloads
from app.chat.state_machine import IllegalTransition, apply_event
from app.models.conversation import Conversation
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.message import Message
from app.models.message_citation import MessageCitation
from app.repositories.kb_chunk_repo import live_chunks_query
from app.repositories.message_repo import MessageRepository
from app.services.conversation_types import CommandError
from app.services.grounded_response_types import (
    Citation,
    ProviderStatus,
    ResponseDecision,
    ResponseOutcome,
)
from app.services.knowledge_gap_service import KnowledgeGapService


class GroundedReplyWriter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._messages = MessageRepository(session)

    async def persist(self, conversation: Conversation, decision: ResponseDecision) -> Message:
        citations = decision.citations
        if citations:
            try:
                conversation.state = apply_event(conversation.state, "bot_reply")
            except IllegalTransition as exc:
                raise CommandError("illegal_state") from exc
        chips = visitor_citation_payloads(citations=citations) if citations else []
        inserted = await self._messages.create(
            conversation.id,
            conversation.site_id,
            "bot",
            decision.body,
            source_chunk_ids=list(dict.fromkeys(c.chunk_id for c in citations))
            if citations
            else None,
            snapshot_id=citations[0].snapshot_id if citations else None,
            system_reason=self._system_reason_for(decision),
            source_urls=[str(chip["source_url"]) for chip in chips if chip["source_url"]]
            if citations
            else None,
            source_title=chips[0]["source_title"] if chips else None,
            display_locator=decision.display_locator,
            response_outcome=decision.outcome.value if decision.outcome is not None else None,
            response_reason_code=decision.reason_code,
        )
        conversation.last_message_at = datetime.now(UTC)
        await KnowledgeGapService(self._session).record_miss(conversation, inserted, decision)
        for citation in citations:
            self._session.add(
                MessageCitation(
                    message=inserted,
                    site_id=conversation.site_id,
                    chunk_id=citation.chunk_id,
                    snapshot_id=citation.snapshot_id,
                    response_start=citation.response_start,
                    response_end=citation.response_end,
                    source_start=citation.source_start,
                    source_end=citation.source_end,
                    cited_text=citation.cited_text,
                    source_title=citation.source_title,
                    source_url=citation.source_url,
                )
            )
        if (
            decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER
            or decision.reason_code == "supported_next_step"
        ):
            conversation.fallback_count = 0
        elif (
            decision.reason_code in {"no_evidence", "grounding_reject", "needs_confirmation"}
            or decision.outcome is ResponseOutcome.CLARIFICATION
        ):
            conversation.fallback_count += 1
        elif decision.reason_code == "off_topic":
            conversation.fallback_count = 0
        if decision.offer_handoff and decision.outcome in {
            ResponseOutcome.KNOWLEDGE_GAP,
            ResponseOutcome.PARTIAL_ANSWER,
            ResponseOutcome.BOUNDARY,
            ResponseOutcome.SYNTHESIZED_ANSWER,
            None,
        }:
            # Persist the offer as bot speech; consent on the next visitor turn.
            conversation.fallback_count = max(conversation.fallback_count, 1)
        return inserted

    @staticmethod
    def _system_reason_for(decision: ResponseDecision) -> str:
        if decision.reason_code == "canned_reply":
            return "canned"
        if decision.outcome is ResponseOutcome.CLARIFICATION:
            return "clarify"
        if decision.reason_code == "source_followup":
            return "answer"
        if decision.reason_code == "tech_fail" or (
            decision.provider_status is ProviderStatus.TECH_FAIL
        ):
            return "tech_fail"
        if (
            decision.reason_code == "grounding_reject"
            or decision.outcome is ResponseOutcome.PARTIAL_ANSWER
        ):
            return "insufficient"
        if decision.citations:
            return "answer"
        if decision.outcome is ResponseOutcome.BOUNDARY:
            return "policy_boundary"
        return "insufficient"

    async def citations_live(self, site_id: UUID, citations: list[Citation]) -> bool:
        cited_chunk_ids = sorted(set(citation.chunk_id for citation in citations))
        if not cited_chunk_ids:
            return True
        result = await self._session.execute(
            live_chunks_query(site_id)
            .with_only_columns(KbChunk.id, KbChunk.snapshot_id, KbChunk.site_id)
            .where(KbChunk.id.in_(cited_chunk_ids))
            .order_by(KbChunk.id)
            .with_for_update(read=True, of=[KbChunk, KbPage, KbSource, KbSnapshot])
        )
        rows = result.all()
        by_id = {row.id: row for row in rows}
        if set(cited_chunk_ids) - set(by_id):
            return False
        citation_by_chunk = {citation.chunk_id: citation for citation in citations}
        for chunk_id, row in by_id.items():
            if row.site_id != site_id:
                return False
            citation = citation_by_chunk.get(chunk_id)
            if citation is None or row.snapshot_id != citation.snapshot_id:
                return False
        return True
