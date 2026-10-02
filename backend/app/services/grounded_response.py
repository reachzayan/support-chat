"""Typed, evidence-first decisions for visitor-facing bot replies.

Claude authors normal answers. Deterministic code owns hard control cases,
narrow validation invariants, and safe failure copy — never extractive FAQ prose.
"""
# ruff: noqa: RUF001

from __future__ import annotations

import re
import time
from dataclasses import replace

import structlog

from app.chat.outcome_copy import (
    TECH_FAIL_HUMAN,
    abuse_boundary_line,
    clarify_scope_line,
    injection_boundary_line,
    transfer_offer_line,
)
from app.llm.intent import ABUSE_TOKENS, is_disengage_request
from app.llm.safety_markers import contains_injection_marker
from app.services.bot_trace import record_trace
from app.services.grounded_response_types import (
    Citation,
    EvidenceUnit,
    Provider,
    ProviderStatus,
    RepairProvider,
    ResponseDecision,
    ResponseOutcome,
    TurnContext,
)
from app.services.grounded_response_types import (
    ModelDraft as ModelDraft,
)
from app.services.grounded_response_validation import (
    _LIMITATION_RE,
    _is_clarifying_only,
    _normalize_copy,
    sentence_spans,
    validate_draft,
)
from app.services.grounded_response_validation import (
    uncited_factual_sentences as uncited_factual_sentences,
)
from app.services.kb_tokens import tokenize

log = structlog.get_logger("grounded_response")


_FRUSTRATION_RE = re.compile(r"\b(dumb|useless|stupid|idiot|not helpful|waste of time)\b", re.I)
_SOURCE_FOLLOWUP_RE = re.compile(
    r"which page|what page|which source|"
    r"where did (?:that|this) come from|"
    r"where did you get (?:that|this|those)|"
    r"quote (?:the source|the exact sentence|that sentence|the sentence)|cite (?:your|the) source|"
    r"cite the url|"
    r"list (?:every|all) pages?|which url|what url",
    re.I,
)
_SUBSTANTIVE_REQUEST_RE = re.compile(
    r"[?¿]|\b(?:what|how|why|when|where|which|explain|describe|compare|"
    r"tell me|help me|can i|can you|could you|do you|does|is there)\b",
    re.I,
)
_UNRELATED_TASK_RE = re.compile(
    r"\b(?:malware|ransomware|steal (?:passwords|credentials)|weather forecast|"
    r"write (?:a poem|a song)|recipe for|cook (?:pasta|a meal))\b",
    re.I,
)


def _eligible(units: list[EvidenceUnit]) -> list[EvidenceUnit]:
    return [
        unit for unit in units if unit.enabled and unit.live and unit.answer_mode != "human_only"
    ]


def _safe_sensitive_handoff() -> ResponseDecision:
    return ResponseDecision(
        ResponseOutcome.BOUNDARY,
        "policy_sensitive",
        "For privacy and compliance, a specialist needs to help with that question.",
        offer_handoff=True,
    )


def _direct_handoff() -> ResponseDecision:
    return ResponseDecision(
        ResponseOutcome.BOUNDARY,
        "visitor_request",
        "",
        offer_handoff=True,
    )


def _has_prior_assistant(prior_messages: tuple[dict[str, str], ...]) -> bool:
    return any(
        (message.get("role") == "assistant" and (message.get("content") or "").strip())
        for message in prior_messages
    )


def _is_source_followup(text: str) -> bool:
    return bool(_SOURCE_FOLLOWUP_RE.search(" ".join((text or "").split())))


def history_recap_decision(
    visitor_text: str, prior_messages: tuple[dict[str, str], ...]
) -> ResponseDecision | None:
    request = " ".join((visitor_text or "").casefold().split())
    if not re.search(
        r"(?:remind me|what did i (?:say|tell you)|what .*i originally (?:said|described))",
        request,
    ):
        return None
    first = next(
        (
            " ".join((message.get("content") or "").split())
            for message in prior_messages
            if message.get("role") == "user" and (message.get("content") or "").strip()
        ),
        "",
    )
    if not first:
        return None
    return ResponseDecision(
        ResponseOutcome.SYNTHESIZED_ANSWER,
        "conversation_recap",
        f'You said: "{first[:800]}"',
    )


def _same_kind_miss_count(turn: TurnContext, reason: str) -> int:
    if turn.prior_miss_count <= 0:
        return 0
    prior = turn.prior_miss_reason
    if prior is None:
        return 0
    knowledge_misses = {"grounding_reject", "needs_confirmation"}
    if prior == reason or (prior in knowledge_misses and reason in knowledge_misses):
        return turn.prior_miss_count
    return 0


def _is_canned_clarify(body: str, site_name: str) -> bool:
    return _normalize_copy(body) == _normalize_copy(clarify_scope_line(site_name))


def source_followup_decision(citations: list[Citation]) -> ResponseDecision:
    if not citations:
        return ResponseDecision(
            ResponseOutcome.CLARIFICATION,
            "source_followup",
            "Which detail would you like me to confirm?",
        )
    first = citations[0]
    prefix = f"Source: {first.source_url}\n\n"
    # Preserve one complete evidence passage, never clip its qualifiers.
    body = prefix + first.cited_text
    verified = [replace(first, response_start=len(prefix), response_end=len(body))]
    return ResponseDecision(
        ResponseOutcome.SYNTHESIZED_ANSWER,
        "source_followup",
        body,
        citations=verified,
    )


def _safe_no_evidence(prior_miss_count: int, site_name: str = "") -> ResponseDecision:
    if prior_miss_count <= 0:
        # Without any qualifying passage we cannot establish business scope.
        # Do not assert a product knowledge gap for an unrelated question.
        return ResponseDecision(
            ResponseOutcome.CLARIFICATION,
            "no_evidence",
            clarify_scope_line(site_name),
        )
    return ResponseDecision(
        ResponseOutcome.KNOWLEDGE_GAP,
        "repeated_miss",
        transfer_offer_line(human_enabled=True),
        offer_handoff=True,
    )


def _safe_technical_failure(
    reason: str = "tech_fail", *, request_id: str | None = None
) -> ResponseDecision:
    log.info("grounded_tech_fail", reason=reason)
    return ResponseDecision(
        ResponseOutcome.KNOWLEDGE_GAP,
        "tech_fail",
        TECH_FAIL_HUMAN,
        offer_handoff=True,
        provider_status=ProviderStatus.TECH_FAIL,
        request_id=request_id,
    )


def _safe_grounding_reject(
    *, prior_miss_count: int = 0, request_id: str | None = None
) -> ResponseDecision:
    """Visitor-safe copy when the provider succeeded but draft validation failed.

    Specific reject reason is already on the grounded_draft_reject log line.
    """
    if prior_miss_count <= 0:
        return ResponseDecision(
            ResponseOutcome.KNOWLEDGE_GAP,
            "grounding_reject",
            "I couldn't verify an accurate answer to that question. A specialist can help.",
            offer_handoff=False,
            provider_status=ProviderStatus.OK,
            request_id=request_id,
        )
    return ResponseDecision(
        ResponseOutcome.KNOWLEDGE_GAP,
        "repeated_miss",
        transfer_offer_line(human_enabled=True),
        offer_handoff=True,
        provider_status=ProviderStatus.OK,
        request_id=request_id,
    )


def _elapsed_ms(started_ns: int) -> int:
    return (time.perf_counter_ns() - started_ns) // 1_000_000


class GroundedResponseEngine:
    def __init__(
        self, complete: Provider | None = None, repair: RepairProvider | None = None
    ) -> None:
        self._complete = complete
        self._repair = repair

    def boundary_decision(self, turn: TurnContext) -> ResponseDecision | None:
        """Hard-control cases decided before any answer, canned or generated, is considered."""
        question = (turn.visitor_text or "").strip()
        if turn.sensitive:
            return _safe_sensitive_handoff()
        if turn.explicit_human_request:
            return _direct_handoff()
        if contains_injection_marker(question) or is_disengage_request(question):
            return self._boundary("prompt_injection", turn.site_name)
        # Profanity is tone, not an instruction override. Keep the cheap boundary
        # for insult-only turns; let the provider answer an actual request.
        if not _SUBSTANTIVE_REQUEST_RE.search(question):
            if set(tokenize(question)) & ABUSE_TOKENS:
                return self._boundary("abuse", turn.site_name)
            if _FRUSTRATION_RE.search(question):
                return self._boundary("frustration", turn.site_name)
        if _UNRELATED_TASK_RE.search(question):
            return ResponseDecision(
                ResponseOutcome.BOUNDARY, "off_topic", clarify_scope_line(turn.site_name)
            )
        return None

    async def respond(  # noqa: C901
        self,
        turn: TurnContext,
        stage_timings: dict[str, int] | None = None,
    ) -> ResponseDecision:
        timings = stage_timings if stage_timings is not None else {}
        boundary = self.boundary_decision(turn)
        if boundary is not None:
            return boundary
        evidence = _eligible(turn.evidence)
        if not evidence:
            return _safe_no_evidence(_same_kind_miss_count(turn, "no_evidence"), turn.site_name)

        if self._complete is None:
            return _safe_technical_failure(reason="provider_unavailable")
        try:
            draft = await self._complete(turn, evidence)
        except Exception:
            return _safe_technical_failure(reason="provider_exception")
        if draft is None or not draft.body.strip():
            return _safe_technical_failure(reason="empty_draft")

        started = time.perf_counter_ns()
        record_trace("draft", draft=draft)
        validation = validate_draft(draft, evidence, turn)
        record_trace(
            "validation",
            accepted=validation.accepted,
            reason=validation.reason,
            validated_draft=validation.draft,
        )
        timings["validate"] = _elapsed_ms(started)
        if validation.reason == "uncited_response_text" and self._repair is not None:
            record_trace(
                "citation_repair",
                attempted=True,
                original_draft=draft,
                uncited_sentences=uncited_factual_sentences(draft),
            )
            started = time.perf_counter_ns()
            try:
                repaired = await self._repair(turn, evidence, draft)
            except Exception:
                repaired = None
            timings["citation_repair"] = _elapsed_ms(started)
            if repaired is not None and repaired.body.strip():
                draft = repaired
                started = time.perf_counter_ns()
                validation = validate_draft(draft, evidence, turn)
                timings["validate"] += _elapsed_ms(started)
            record_trace(
                "citation_repair",
                accepted=validation.accepted,
                reason=validation.reason,
                repaired_draft=repaired,
            )
            record_trace(
                "validation",
                accepted=validation.accepted,
                reason=validation.reason,
                validated_draft=validation.draft,
            )
        if not validation.accepted or validation.draft is None:
            return _safe_grounding_reject(
                prior_miss_count=_same_kind_miss_count(turn, "grounding_reject"),
                request_id=draft.request_id,
            )
        if _is_canned_clarify(validation.draft.body, turn.site_name):
            return ResponseDecision(
                ResponseOutcome.BOUNDARY,
                "off_topic",
                validation.draft.body,
                provider_status=ProviderStatus.OK,
                request_id=draft.request_id,
            )

        unresolved = any(
            _LIMITATION_RE.search(sentence.group().strip())
            and not (
                validation.draft.citations
                and re.match(
                    r"^(?:a|our) specialist can (?:help|review|discuss)\b",
                    sentence.group().strip(),
                    re.I,
                )
            )
            for sentence in sentence_spans(validation.draft.body)
        )
        record_trace(
            "answer_quality",
            grounding_accepted=True,
            explicit_unresolved_detail=unresolved,
            resolution="unresolved" if unresolved else "no_explicit_gap",
        )
        if unresolved:
            body = validation.draft.body
            asked_transfer = bool(re.search(r"would you like (?:me to )?connect you\b", body, re.I))
            repeated = _same_kind_miss_count(turn, "needs_confirmation") > 0
            offer = asked_transfer or repeated
            if repeated and not asked_transfer:
                body += "\n\n" + transfer_offer_line(human_enabled=True)
            return ResponseDecision(
                ResponseOutcome.PARTIAL_ANSWER
                if validation.draft.citations
                else ResponseOutcome.KNOWLEDGE_GAP,
                "needs_confirmation",
                body,
                citations=validation.draft.citations,
                offer_handoff=offer,
                provider_status=ProviderStatus.OK,
                request_id=draft.request_id,
            )

        outcome = (
            ResponseOutcome.CLARIFICATION
            if _is_clarifying_only(validation.draft.body)
            else ResponseOutcome.SYNTHESIZED_ANSWER
        )
        return ResponseDecision(
            outcome,
            None,
            validation.draft.body,
            citations=validation.draft.citations,
            provider_status=ProviderStatus.OK,
            request_id=validation.draft.request_id,
        )

    @staticmethod
    def _boundary(reason: str, site_name: str = "") -> ResponseDecision:
        if reason == "frustration":
            body = (
                "I’m sorry—that wasn’t helpful. Tell me what you need confirmed, "
                "or I can connect you with a specialist."
            )
        elif reason == "abuse":
            body = abuse_boundary_line(site_name)
        elif reason == "prompt_injection":
            body = injection_boundary_line(site_name)
        else:
            body = clarify_scope_line(site_name)
        return ResponseDecision(
            ResponseOutcome.BOUNDARY,
            reason,
            body,
            offer_handoff=reason == "frustration",
        )
