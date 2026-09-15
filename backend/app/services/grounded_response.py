"""Typed, evidence-first decisions for visitor-facing bot replies.

Claude authors normal answers. Deterministic code owns hard control cases,
narrow validation invariants, and safe failure copy — never extractive FAQ prose.
"""
# ruff: noqa: RUF001

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

import structlog

from app.chat.outcome_copy import (
    INSUFFICIENT_HUMAN,
    TECH_FAIL_HUMAN,
    UNCITED_ADVISORY_SUFFIX,
    handoff_copy,
)
from app.llm.intent import is_disengage_request, is_unrelated_request
from app.llm.safety_markers import contains_injection_marker
from app.services import output_validator
from app.services.kb_tokens import tokenize

log = structlog.get_logger("grounded_response")


class ResponseOutcome(StrEnum):
    EXACT_ANSWER = "exact_answer"  # Deprecated: no longer produced by respond().
    SYNTHESIZED_ANSWER = "synthesized_answer"
    CLARIFICATION = "clarification"
    PARTIAL_ANSWER = "partial_answer"  # Schema constant; retained for migration 20 check.
    KNOWLEDGE_GAP = "knowledge_gap"
    BOUNDARY = "boundary"


class ProviderStatus(StrEnum):
    NOT_USED = "not_used"
    OK = "ok"
    TECH_FAIL = "tech_fail"


@dataclass(frozen=True)
class EvidenceUnit:
    id: UUID
    canonical_question: str | None
    aliases: tuple[str, ...]
    topic_label: str
    answer_verbatim: str
    source_title: str
    source_url: str
    snapshot_id: UUID | None = None
    risk_class: str = "general"
    answer_mode: str = "paraphrase_allowed"
    enabled: bool = True
    live: bool = True


@dataclass(frozen=True)
class Citation:
    chunk_id: UUID
    snapshot_id: UUID | None
    response_start: int
    response_end: int
    source_start: int
    source_end: int
    cited_text: str
    source_title: str
    source_url: str


@dataclass(frozen=True)
class TurnContext:
    visitor_text: str
    evidence: list[EvidenceUnit]
    site_name: str = ""
    grounding_text: str | None = None
    prior_messages: tuple[dict[str, str], ...] = ()
    explicit_human_request: bool = False
    sensitive: bool = False
    site_capability_labels: tuple[str, ...] = ()
    off_brand_blocklist: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResponseDecision:
    outcome: ResponseOutcome | None
    reason_code: str | None
    body: str
    citations: list[Citation] = field(default_factory=list)
    offer_handoff: bool = False
    provider_status: ProviderStatus = ProviderStatus.NOT_USED
    request_id: str | None = None


@dataclass(frozen=True)
class ModelDraft:
    body: str
    citations: list[Citation]
    request_id: str | None = None


@dataclass(frozen=True)
class DraftValidation:
    accepted: bool
    reason: str
    draft: ModelDraft | None = None


Provider = Callable[[TurnContext, list[EvidenceUnit]], Awaitable[ModelDraft | None]]

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_FRUSTRATION_RE = re.compile(r"\b(dumb|useless|stupid|idiot|not helpful|waste of time)\b", re.I)
_ABUSE_RE = re.compile(r"\b(fuck|shit|bitch|asshole)\b", re.I)
_NUMERIC_CLAIM_RE = re.compile(
    r"\$\d+(?:\.\d{1,2})?|\b\d+(?:[-–]\d+)?\s*"
    r"(?:hours?|days?|minutes?|business days?)|\b\d+(?:\.\d+)?%",
    re.I,
)
_REGULATED_RE = re.compile(r"\b(?:DOT|USDOT|FMCSA|FCRA|HIPAA|49\s+CFR\s+Part\s+40)\b", re.I)
_MAX_CHARS = 1500
_SOFT_WORD_CAP = 120


def normalized_question(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    normalized = _PUNCT_RE.sub(" ", normalized)
    return " ".join(normalized.split())


def contextual_grounding_query(
    visitor_text: str, prior_messages: tuple[dict[str, str], ...]
) -> str:
    """Give short follow-ups enough context for retrieval without rewriting normal turns."""
    if len(tokenize(visitor_text)) >= 3:
        return visitor_text
    for message in reversed(prior_messages):
        if message.get("role") != "assistant":
            continue
        body = (message.get("content") or "").strip()
        if body.endswith("?"):
            return f"{body} {visitor_text}"
        break
    return visitor_text


def _eligible(units: list[EvidenceUnit]) -> list[EvidenceUnit]:
    return [
        unit for unit in units if unit.enabled and unit.live and unit.answer_mode != "human_only"
    ]


def _numbers_are_verbatim(body: str, cited_text: str) -> bool:
    source = " ".join(cited_text.casefold().split())
    return all(
        " ".join(token.casefold().split()) in source for token in _NUMERIC_CLAIM_RE.findall(body)
    )


def _regulated_literals_are_verbatim(body: str, cited_text: str) -> bool:
    source = " ".join(cited_text.casefold().split())
    return all(
        " ".join(token.casefold().split()) in source for token in _REGULATED_RE.findall(body)
    )


def _is_clarifying_only(body: str) -> bool:
    text = (body or "").strip()
    if not text.endswith("?"):
        return False
    # Single sentence: no internal sentence terminators before the final '?'.
    without_final = text[:-1].rstrip()
    if re.search(r"[.!?]", without_final):
        return False
    if _NUMERIC_CLAIM_RE.search(text) or _REGULATED_RE.search(text):
        return False
    return True


def _normalize_copy(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _is_source_copy(body: str, units: list[EvidenceUnit]) -> bool:
    norm = _normalize_copy(body)
    verbatim = {_normalize_copy(unit.answer_verbatim) for unit in units if unit.answer_verbatim}
    verbatim.discard("")
    if not verbatim:
        return False
    if norm in verbatim:
        return True
    fragments = [fragment for fragment in re.split(r"\n\s*\n", body) if fragment.strip()]
    if len(fragments) < 2:
        return False
    return all(_normalize_copy(fragment) in verbatim for fragment in fragments)


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


def _safe_no_evidence_handoff() -> ResponseDecision:
    return ResponseDecision(
        ResponseOutcome.KNOWLEDGE_GAP,
        "no_evidence",
        handoff_copy("retrieval_miss", human_enabled=True),
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


def _safe_grounding_reject(reason: str, *, request_id: str | None = None) -> ResponseDecision:
    """Visitor-safe copy when the provider succeeded but draft validation failed.

    Specific reject reason is already on the grounded_draft_reject log line.
    """
    del reason
    return ResponseDecision(
        ResponseOutcome.KNOWLEDGE_GAP,
        "grounding_reject",
        INSUFFICIENT_HUMAN,
        offer_handoff=True,
        provider_status=ProviderStatus.OK,
        request_id=request_id,
    )


def _uncited_advisory(draft: ModelDraft) -> ResponseDecision:
    body = draft.body.strip()
    return ResponseDecision(
        ResponseOutcome.SYNTHESIZED_ANSWER,
        "uncited_advisory",
        f"{body}\n\n{UNCITED_ADVISORY_SUFFIX}",
        citations=[],
        offer_handoff=True,
        provider_status=ProviderStatus.OK,
        request_id=draft.request_id,
    )


def _elapsed_ms(started_ns: int) -> int:
    return (time.perf_counter_ns() - started_ns) // 1_000_000


class GroundedResponseEngine:
    def __init__(self, complete: Provider | None = None) -> None:
        self._complete = complete

    async def respond(  # noqa: C901
        self,
        turn: TurnContext,
        stage_timings: dict[str, int] | None = None,
    ) -> ResponseDecision:
        timings = stage_timings if stage_timings is not None else {}
        question = (turn.visitor_text or "").strip()
        grounding_question = (turn.grounding_text or question).strip()
        if turn.sensitive:
            return _safe_sensitive_handoff()
        if turn.explicit_human_request:
            return _direct_handoff()
        if _ABUSE_RE.search(question):
            return self._boundary("abuse")
        if contains_injection_marker(question) or is_disengage_request(question):
            return self._boundary("prompt_injection")
        if _FRUSTRATION_RE.search(question):
            return self._boundary("frustration")

        evidence = _eligible(turn.evidence)
        if not evidence:
            if not turn.evidence and is_unrelated_request(grounding_question):
                return self._boundary("off_topic", turn)
            return _safe_no_evidence_handoff()

        if self._complete is None:
            return _safe_technical_failure(reason="provider_unavailable")
        try:
            draft = await self._complete(turn, evidence[:5])
        except Exception:
            return _safe_technical_failure(reason="provider_exception")
        if draft is None or not draft.body.strip():
            return _safe_technical_failure(reason="empty_draft")

        body = draft.body.strip()
        # Uncited non-clarifying answers: keep source_copy as a hard reject, otherwise
        # show Claude's body with an advisory suffix (do not tech-fail).
        if not draft.citations and not _is_clarifying_only(body):
            if _is_source_copy(body, evidence):
                self._reject("source_copy", draft)
                return _safe_grounding_reject(reason="source_copy", request_id=draft.request_id)
            return _uncited_advisory(draft)

        started = time.perf_counter_ns()
        validation = self._validate_draft(draft, evidence, turn)
        timings["validate"] = _elapsed_ms(started)
        if not validation.accepted or validation.draft is None:
            return _safe_grounding_reject(reason=validation.reason, request_id=draft.request_id)

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

    def _validate_draft(  # noqa: C901
        self,
        draft: ModelDraft,
        units: list[EvidenceUnit],
        turn: TurnContext,
    ) -> DraftValidation:
        body = draft.body.strip()
        citations = list(draft.citations)
        if not body:
            return self._reject("empty", draft)
        if len(body) > _MAX_CHARS:
            return self._reject("over_length", draft)
        if len(body.split()) > _SOFT_WORD_CAP:
            return self._reject("over_words", draft)

        clarifying = _is_clarifying_only(body)
        # Citation absence for non-clarifying drafts is handled in respond() as
        # uncited_advisory (or source_copy). Do not reject no_citation here.

        if _is_source_copy(body, units):
            return self._reject("source_copy", draft)

        allowed = {unit.id: unit for unit in units}
        cited_text = ""
        for citation in citations:
            unit = allowed.get(citation.chunk_id)
            if unit is None:
                return self._reject("cite_off_corpus", draft)
            if citation.snapshot_id != unit.snapshot_id:
                return self._reject("snapshot_mismatch", draft)
            if citation.response_start < 0 or citation.response_end > len(body):
                return self._reject("response_offset", draft)
            if citation.response_start > citation.response_end:
                return self._reject("response_offset", draft)
            cited_text += citation.cited_text

        if not _numbers_are_verbatim(body, cited_text):
            return self._reject("unsupported_numeric", draft)
        if not _regulated_literals_are_verbatim(body, cited_text):
            return self._reject("unsupported_regulated", draft)

        safety = output_validator.evaluate(
            body,
            allowed_ids=[unit.id for unit in units],
            cited=[citation.chunk_id for citation in citations],
            citation_urls=[citation.source_url for citation in citations],
            live_urls={unit.source_url for unit in units if unit.source_url},
            cited_answer_text=cited_text,
            off_brand_blocklist=list(turn.off_brand_blocklist),
            max_chars=_MAX_CHARS,
            curated_refusal=clarifying,
        )
        if not safety.accepted:
            return self._reject(safety.reason, draft)

        return DraftValidation(
            accepted=True,
            reason="accepted",
            draft=ModelDraft(body=body, citations=citations, request_id=draft.request_id),
        )

    @staticmethod
    def _reject(reason: str, draft: ModelDraft) -> DraftValidation:
        log.info(
            "grounded_draft_reject",
            reason=reason,
            citation_count=len(draft.citations),
            body_chars=len(draft.body or ""),
        )
        return DraftValidation(accepted=False, reason=reason)

    @staticmethod
    def _boundary(reason: str, turn: TurnContext | None = None) -> ResponseDecision:
        if reason == "frustration":
            body = (
                "I’m sorry—that wasn’t helpful. Tell me what you need confirmed, "
                "or I can connect you with a specialist."
            )
        elif reason == "abuse":
            body = (
                "I’m here to help with screening and compliance questions. "
                "We can continue when the conversation stays respectful."
            )
        elif reason == "prompt_injection":
            body = (
                "I can help with screening and compliance questions. What would you like to know?"
            )
        else:
            labels: list[str] = []
            if turn is not None:
                for label in turn.site_capability_labels or [
                    unit.topic_label for unit in turn.evidence
                ]:
                    display = (label or "").strip().rstrip("?!.")
                    if not display:
                        continue
                    if re.match(
                        r"^(?:are|can|do|does|how|is|what|when|where|why|who)\b", display, re.I
                    ):
                        continue
                    if display not in labels:
                        labels.append(display)
            topic = ", ".join(labels[:3]) if labels else "screening and compliance"
            topic = topic.rstrip("?")
            body = (
                "I can help with screening and compliance questions. "
                f"What would you like to know about {topic}?"
            )
        return ResponseDecision(
            ResponseOutcome.BOUNDARY,
            reason,
            body,
            offer_handoff=reason == "frustration",
        )
