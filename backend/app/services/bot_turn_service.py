"""Prepare a grounded reply from history, evidence and provider output.

ConversationService alone owns generation leases, transitions and persistence.
"""

import asyncio
import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.bot_responder import BotResponder
from app.llm.intent import (
    is_handoff_declined,
)
from app.llm.prompts import document_body
from app.models.conversation import Conversation
from app.models.kb_chunk import KbChunk
from app.models.message import Message
from app.models.site import Site
from app.repositories.kb_chunk_repo import live_chunks_query
from app.repositories.message_repo import MessageRepository
from app.services.bot_trace import record_trace
from app.services.full_context import prior_provider_messages
from app.services.grounded_response import (
    Citation,
    EvidenceUnit,
    GroundedResponseEngine,
    ModelDraft,
    ResponseDecision,
    TurnContext,
    _has_prior_assistant,
    _is_source_followup,
    history_recap_decision,
)
from app.services.kb_embedder import default_embedder
from app.services.kb_hybrid import HybridKbSearch
from app.services.pii_redactor import redact_for_model
from app.services.route_decision import live_snapshots_for_site
from app.settings import get_settings

MAX_TURN_EVIDENCE = 8
MAX_CARRIED_EVIDENCE = 2


@dataclass
class PreparedBotReply:
    decision: ResponseDecision
    stage_timings: dict[str, int]


class BotTurnService:
    def __init__(
        self, session: AsyncSession, responder=None, embedder=None, *, evidence_loader=None
    ) -> None:
        self._session = session
        self._messages = MessageRepository(session)
        self._responder = responder if responder is not None else BotResponder()
        self._embedder = embedder if embedder is not None else default_embedder()
        self._evidence_loader = evidence_loader or self.retrieve_evidence

    async def prepare(
        self,
        conversation: Conversation,
        site: Site,
        visitor_text: str,
    ) -> PreparedBotReply:
        conversation_id = conversation.id
        stage_timings: dict[str, int] = {
            "history_load": 0,
            "lexical_retrieve": 0,
            "trigram_retrieve": 0,
            "dense_retrieve": 0,
            "embed": 0,
            "provider": 0,
            "citation_parse": 0,
            "validate": 0,
            "liveness_check": 0,
            "commit": 0,
        }
        started = time.perf_counter_ns()
        window = await self._messages.list_recent_roles(
            conversation_id,
            {"visitor", "bot"},
            get_settings().conversation_window_size + 1,
        )
        prior_messages = tuple(prior_provider_messages(window, visitor_text))
        stage_timings["history_load"] = (time.perf_counter_ns() - started) // 1_000_000
        recap = history_recap_decision(visitor_text, prior_messages)
        if recap is not None:
            return PreparedBotReply(recap, stage_timings)
        if _is_source_followup(visitor_text) and _has_prior_assistant(prior_messages):
            from app.services.grounded_response import source_followup_decision

            previous = next((row for row in reversed(window) if row.role == "bot"), None)
            citations = [
                Citation(
                    c.chunk_id,
                    c.snapshot_id,
                    c.response_start,
                    c.response_end,
                    c.source_start,
                    c.source_end,
                    c.cited_text,
                    c.source_title,
                    c.source_url,
                )
                for c in (previous.citations if previous else [])
            ]
            return PreparedBotReply(source_followup_decision(citations), stage_timings)
        record_trace("history", prior_messages=prior_messages)
        # Retrieval answers the current message exactly as written. Conversation
        # continuity comes from live evidence cited by the previous bot answer,
        # not from guessing whether this wording looks like a follow-up.
        record_trace("retrieval", query=redact_for_model(visitor_text))
        current_evidence = await self._evidence_loader(site.id, visitor_text, stage_timings)
        carried_evidence = await self._load_carried_evidence(site.id, window)
        evidence = self._merge_evidence(current_evidence, carried_evidence)
        record_trace(
            "retrieval",
            current_evidence_ids=[unit.id for unit in current_evidence],
            carried_evidence_ids=[unit.id for unit in carried_evidence],
            evidence=evidence,
        )
        record_trace(
            "classification",
            evidence_topics=list(dict.fromkeys(unit.topic_label for unit in evidence)),
            intent_role="diagnostic_only",
        )
        handoff_declined = any(
            row.role == "visitor" and is_handoff_declined(row.body or "") for row in window
        )
        record_trace("classification", handoff_declined=handoff_declined)
        decision = await self._grounded_response_engine(site, stage_timings).respond(
            TurnContext(
                visitor_text=visitor_text,
                evidence=evidence,
                site_name=site.name,
                prior_messages=prior_messages,
                prior_miss_count=0 if handoff_declined else conversation.fallback_count,
                prior_miss_reason=self._last_bot_reason(window, conversation.fallback_count),
                off_brand_blocklist=tuple(getattr(site, "off_brand_blocklist", None) or ()),
            ),
            stage_timings=stage_timings,
        )
        return PreparedBotReply(decision, stage_timings)

    async def _load_carried_evidence(
        self,
        site_id: UUID,
        window: list[Message],
    ) -> list[EvidenceUnit]:
        previous = next(
            (row for row in reversed(window) if row.role == "bot" and row.citations),
            None,
        )
        if previous is None:
            return []

        citations = [citation for citation in previous.citations if citation.chunk_id is not None]
        chunk_ids = list(dict.fromkeys(citation.chunk_id for citation in citations))[
            :MAX_CARRIED_EVIDENCE
        ]
        if not chunk_ids:
            return []
        result = await self._session.execute(
            live_chunks_query(site_id).where(KbChunk.id.in_(chunk_ids))
        )
        by_id = {chunk.id: (chunk, page) for chunk, page in result.all()}
        metadata = {citation.chunk_id: citation for citation in citations}
        carried: list[EvidenceUnit] = []
        for chunk_id in chunk_ids:
            row = by_id.get(chunk_id)
            citation = metadata.get(chunk_id)
            if row is None or citation is None:
                continue
            chunk, page = row
            carried.append(
                EvidenceUnit(
                    id=chunk.id,
                    canonical_question=chunk.canonical_question,
                    aliases=tuple(chunk.aliases or ()),
                    topic_label=chunk.topic_label or chunk.heading,
                    answer_verbatim=chunk.answer_verbatim or chunk.body,
                    source_title=citation.source_title or page.title,
                    source_url=citation.source_url or page.public_url,
                    snapshot_id=chunk.snapshot_id,
                    risk_class=chunk.risk_class,
                    answer_mode=chunk.answer_mode,
                    enabled=chunk.enabled,
                    live=True,
                    source_heading="" if chunk.context_prefix else chunk.heading,
                )
            )
        return carried

    @staticmethod
    def _merge_evidence(
        current: list[EvidenceUnit],
        carried: list[EvidenceUnit],
    ) -> list[EvidenceUnit]:
        """Reserve a small continuity budget while keeping current-topic evidence last."""
        current_ids = {unit.id for unit in current}
        continuity = [unit for unit in carried if unit.id not in current_ids][:MAX_CARRIED_EVIDENCE]
        current_budget = MAX_TURN_EVIDENCE - len(continuity)
        return [*continuity, *current[:current_budget]]

    def _grounded_response_engine(
        self, site: Site, stage_timings: dict[str, int]
    ) -> GroundedResponseEngine:
        complete = getattr(self._responder, "generate_grounded_draft", None)
        # BotResponder(complete=...) test doubles still use the legacy adapter.
        if complete is not None and getattr(self._responder, "_complete", None) is not None:
            complete = None
        if complete is None:

            async def complete(turn, units):
                return await self._legacy_grounded_draft(site, turn, units)

        else:
            original_complete = complete

            async def complete(turn, units):
                try:
                    return await original_complete(turn, units, stage_timings=stage_timings)
                except TypeError:
                    return await original_complete(turn, units)

        repair_draft = getattr(self._responder, "repair_grounded_draft", None)
        repair = None
        if repair_draft is not None and getattr(self._responder, "_complete", None) is None:
            provider_deadline = time.monotonic() + get_settings().anthropic_timeout

            async def repair(turn, units, draft):
                remaining = provider_deadline - time.monotonic()
                if remaining <= 0:
                    record_trace("citation_repair", budget_exhausted=True)
                    return None
                async with asyncio.timeout(remaining):
                    return await repair_draft(turn, units, draft, stage_timings=stage_timings)

        return GroundedResponseEngine(complete=complete, repair=repair)

    async def retrieve_evidence(
        self,
        site_id: UUID,
        visitor_text: str,
        stage_timings: dict[str, int] | None = None,
    ) -> list[EvidenceUnit]:
        snapshots = await live_snapshots_for_site(self._session, site_id)
        if not snapshots:
            return []
        hits = await HybridKbSearch(self._session).search_with_deferred_embed(
            self._embedder,
            site_id,
            visitor_text,
            stage_timings=stage_timings,
        )
        return [
            EvidenceUnit(
                id=hit.id,
                canonical_question=hit.canonical_question,
                aliases=tuple(hit.aliases or ()),
                topic_label=hit.topic_label or hit.heading,
                answer_verbatim=hit.answer_verbatim or hit.body,
                source_title=hit.title,
                source_url=hit.url,
                snapshot_id=hit.snapshot_id,
                risk_class=hit.risk_class,
                answer_mode=hit.answer_mode,
                enabled=hit.enabled,
                live=True,
                source_heading="" if hit.structured else hit.heading,
            )
            for hit in hits
        ]

    async def _legacy_grounded_draft(
        self, site: Site, turn: TurnContext, units: list[EvidenceUnit]
    ):
        """Adapt test/custom responders to the typed grounded provider contract."""
        chunk_ids = [unit.id for unit in units]
        result = await self._session.execute(
            live_chunks_query(site.id).where(KbChunk.id.in_(chunk_ids))
        )
        by_id = {chunk.id: (chunk, page) for chunk, page in result.all()}
        documents = [by_id[unit.id][0] for unit in units if unit.id in by_id]
        generate_from_documents = getattr(self._responder, "generate_from_documents", None)
        if generate_from_documents is not None:
            answer = await generate_from_documents(
                site=site,
                visitor_text=turn.visitor_text,
                documents=documents,
                prior_messages=list(turn.prior_messages),
            )
        else:
            generate = getattr(self._responder, "generate", None)
            if generate is None:
                return None
            answer = await generate(site, turn.visitor_text, documents)
        if answer is None:
            return None
        body = str(getattr(answer, "body", "") or "").strip()
        cited_ids = list(getattr(answer, "source_chunk_ids", None) or [])
        if not getattr(answer, "accepted", False) or not body:
            return ModelDraft(body=body, citations=[])
        citations: list[Citation] = []
        for unit in units:
            if unit.id not in cited_ids:
                continue
            start = body.find(unit.answer_verbatim)
            if start < 0:
                start = 0
                end = len(body)
            else:
                end = start + len(unit.answer_verbatim)
            citations.append(
                Citation(
                    chunk_id=unit.id,
                    snapshot_id=unit.snapshot_id,
                    response_start=start,
                    response_end=end,
                    source_start=0,
                    source_end=len(document_body(unit)),
                    cited_text=document_body(unit),
                    source_title=unit.source_title,
                    source_url=unit.source_url,
                )
            )
        return ModelDraft(body=body, citations=citations)

    @staticmethod
    def _last_bot_reason(window: list[Message], fallback_count: int) -> str | None:
        if fallback_count <= 0:
            return None
        for row in reversed(window):
            if row.role == "bot" and row.response_reason_code:
                return row.response_reason_code
        return None
