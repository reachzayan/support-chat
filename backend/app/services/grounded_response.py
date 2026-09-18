"""Typed, evidence-first decisions for visitor-facing bot replies.

Claude authors normal answers. Deterministic code owns hard control cases,
narrow validation invariants, and safe failure copy — never extractive FAQ prose.
"""
# ruff: noqa: RUF001

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from enum import StrEnum
from uuid import UUID

import structlog

from app.chat.outcome_copy import (
    TECH_FAIL_HUMAN,
    abuse_boundary_line,
    clarify_scope_line,
    handoff_copy,
    injection_boundary_line,
    keep_helping_line,
)
from app.llm.intent import is_disengage_request
from app.llm.prompts import document_body
from app.llm.safety_markers import contains_injection_marker
from app.services import output_validator
from app.services.pii_redactor import redact_for_model

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
    source_heading: str = ""


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
    prior_messages: tuple[dict[str, str], ...] = ()
    prior_miss_count: int = 0
    prior_miss_reason: str | None = None
    explicit_human_request: bool = False
    sensitive: bool = False
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

_FRUSTRATION_RE = re.compile(r"\b(dumb|useless|stupid|idiot|not helpful|waste of time)\b", re.I)
_SOURCE_FOLLOWUP_RE = re.compile(
    r"which page|what page|which source|"
    r"where did (?:that|this) come from|"
    r"where did you get (?:that|this|those)|"
    r"quote the source|cite (?:your|the) source|"
    r"cite the url|"
    r"list (?:every|all) pages?|which url|what url",
    re.I,
)
_ABUSE_RE = re.compile(r"\b(fuck|shit|bitch|asshole)\b", re.I)
_NUMERIC_CLAIM_RE = re.compile(
    r"\$\d+(?:\.\d{1,2})?|\b\d+(?:[-–]\d+)?\s*"
    r"(?:hours?|days?|minutes?|business days?)|\b\d+(?:\.\d+)?%",
    re.I,
)
_REGULATED_RE = re.compile(r"\b(?:DOT|USDOT|FMCSA|FCRA|HIPAA|49\s+CFR\s+Part\s+40)\b", re.I)
_MAX_CHARS = 1500
_KEEPABLE_GAPS = frozenset(
    {
        "yes",
        "no",
        "and",
        "also",
        "including",
        "these include",
        "our services include",
    }
)
_SOFT_WORD_CAP = 120
_COURTESY_EDGE_RE = re.compile(
    r"^(?:"
    r"happy to help(?: you(?: today)?)?"
    r"|glad (?:to help|i could help)"
    r"|i(?:['’]m| am) happy to help"
    r"|i(?:['’]d| would) be happy to help"
    r"|sure(?: thing)?"
    r"|of course"
    r"|absolutely"
    r"|certainly"
    r"|great(?: question)?"
    r"|good question"
    r"|thanks(?: for (?:asking|reaching out))?"
    r"|thank you"
    r"|you(?:['’]re| are) welcome"
    r"|let me know if you (?:need|have) (?:anything(?: else)?|questions?)"
    r"|hope (?:that|this) helps"
    r")[.!]*$",
    re.I,
)


def contextual_grounding_query(
    visitor_text: str, prior_messages: tuple[dict[str, str], ...]
) -> str:
    """Ground retrieval in the latest exchange instead of isolated fragments."""
    for message in reversed(prior_messages):
        if message.get("role") != "assistant":
            continue
        body = (message.get("content") or "").strip()
        if body:
            return f"{body} {visitor_text}"
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


def _is_disallowed_source_copy(
    body: str, units: list[EvidenceUnit], citations: list[Citation]
) -> bool:
    norm = _normalize_copy(body)
    exact_units = {
        unit.id
        for unit in units
        if unit.answer_verbatim and _normalize_copy(unit.answer_verbatim) == norm
    }
    if exact_units:
        return not citations

    verbatim = {_normalize_copy(unit.answer_verbatim) for unit in units if unit.answer_verbatim}
    verbatim.discard("")
    if not verbatim:
        return False
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


def _is_courtesy_edge(text: str) -> bool:
    compact = " ".join((text or "").split())
    if not compact:
        return True
    return bool(_COURTESY_EDGE_RE.fullmatch(compact))


def _trim_uncited_edges(body: str, citations: list[Citation]) -> tuple[str, list[Citation]]:
    if not body or not citations:
        return body, citations
    start = min(item.response_start for item in citations)
    end = max(item.response_end for item in citations)
    start = max(0, min(start, len(body)))
    end = max(start, min(end, len(body)))
    if start == 0 and end == len(body):
        return body, citations
    if not _is_courtesy_edge(body[:start]):
        start = 0
    if not _is_courtesy_edge(body[end:]):
        end = len(body)
    if start == 0 and end == len(body):
        return body, citations

    trimmed = body[start:end]
    shifted = [
        replace(
            item,
            response_start=item.response_start - start,
            response_end=item.response_end - start,
        )
        for item in citations
    ]
    return trimmed, shifted


def _is_keepable_gap(text: str) -> bool:
    stripped = (text or "").strip()
    if not re.search(r"\w", stripped):
        return True
    connective = " ".join(stripped.casefold().split()).strip(".!:;, ")
    return connective in _KEEPABLE_GAPS or _is_clarifying_only(stripped)


def _citation_spans(body: str, citations: list[Citation]) -> list[tuple[int, int, Citation | None]]:
    pieces: list[tuple[int, int, Citation | None]] = []
    cursor = 0
    ordered = sorted(citations, key=lambda item: (item.response_start, item.response_end))
    for citation in ordered:
        start = max(0, min(citation.response_start, len(body)))
        end = max(start, min(citation.response_end, len(body)))
        if end <= cursor:
            continue
        start = max(start, cursor)
        if start > cursor:
            pieces.append((cursor, start, None))
        pieces.append((start, end, citation))
        cursor = end
    if cursor < len(body):
        pieces.append((cursor, len(body), None))
    return pieces


def _drop_uncited_spans(body: str, citations: list[Citation]) -> tuple[str, list[Citation]]:
    if not body or not citations:
        return body, citations
    parts: list[str] = []
    shifted: list[Citation] = []
    pos = 0
    for start, end, citation in _citation_spans(body, citations):
        segment = body[start:end]
        if citation is None and not _is_keepable_gap(segment):
            continue
        if parts and not parts[-1][-1:].isspace() and segment and not segment[0].isspace():
            parts.append(" ")
            pos += 1
        if citation is not None:
            shifted.append(replace(citation, response_start=pos, response_end=pos + len(segment)))
        parts.append(segment)
        pos += len(segment)
    return "".join(parts), shifted


def _has_prior_assistant(prior_messages: tuple[dict[str, str], ...]) -> bool:
    return any(
        (message.get("role") == "assistant" and (message.get("content") or "").strip())
        for message in prior_messages
    )


def _is_source_followup(text: str) -> bool:
    return bool(_SOURCE_FOLLOWUP_RE.search(" ".join((text or "").split())))


def _same_kind_miss_count(turn: TurnContext, reason: str) -> int:
    if turn.prior_miss_count <= 0:
        return 0
    prior = turn.prior_miss_reason
    if prior is None:
        return 0
    if prior == reason:
        return turn.prior_miss_count
    return 0


def _is_canned_clarify(body: str, site_name: str) -> bool:
    return _normalize_copy(body) == _normalize_copy(clarify_scope_line(site_name))


def _safe_source_followup(site_name: str = "") -> ResponseDecision:
    return ResponseDecision(
        ResponseOutcome.SYNTHESIZED_ANSWER,
        "source_followup",
        keep_helping_line(site_name),
    )


def _safe_no_evidence(prior_miss_count: int, site_name: str = "") -> ResponseDecision:
    if prior_miss_count <= 0:
        return ResponseDecision(
            ResponseOutcome.CLARIFICATION,
            "no_evidence",
            clarify_scope_line(site_name),
        )
    return ResponseDecision(
        ResponseOutcome.KNOWLEDGE_GAP,
        "repeated_miss",
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


def _safe_grounding_reject(
    reason: str,
    *,
    prior_miss_count: int = 0,
    site_name: str = "",
    request_id: str | None = None,
) -> ResponseDecision:
    """Visitor-safe copy when the provider succeeded but draft validation failed.

    Specific reject reason is already on the grounded_draft_reject log line.
    """
    del reason
    if prior_miss_count <= 0:
        return ResponseDecision(
            ResponseOutcome.CLARIFICATION,
            "grounding_reject",
            clarify_scope_line(site_name),
            offer_handoff=False,
            provider_status=ProviderStatus.OK,
            request_id=request_id,
        )
    return ResponseDecision(
        ResponseOutcome.KNOWLEDGE_GAP,
        "repeated_miss",
        handoff_copy("repeated_miss", human_enabled=True),
        offer_handoff=True,
        provider_status=ProviderStatus.OK,
        request_id=request_id,
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
        if turn.sensitive:
            return _safe_sensitive_handoff()
        if turn.explicit_human_request:
            return _direct_handoff()
        if _ABUSE_RE.search(question):
            return self._boundary("abuse", turn.site_name)
        if contains_injection_marker(question) or is_disengage_request(question):
            return self._boundary("prompt_injection", turn.site_name)
        if _FRUSTRATION_RE.search(question):
            return self._boundary("frustration", turn.site_name)
        if _is_source_followup(question) and _has_prior_assistant(turn.prior_messages):
            return _safe_source_followup(turn.site_name)

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
        validation = self._validate_draft(draft, evidence, turn)
        timings["validate"] = _elapsed_ms(started)
        if not validation.accepted or validation.draft is None:
            return _safe_grounding_reject(
                reason=validation.reason,
                prior_miss_count=_same_kind_miss_count(turn, "grounding_reject"),
                site_name=turn.site_name,
                request_id=draft.request_id,
            )
        if _is_canned_clarify(validation.draft.body, turn.site_name):
            return _safe_no_evidence(_same_kind_miss_count(turn, "no_evidence"), turn.site_name)

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

        allowed = {unit.id: unit for unit in units}
        cited_parts: list[str] = []
        for citation in citations:
            unit = allowed.get(citation.chunk_id)
            if unit is None:
                return self._reject("cite_off_corpus", draft)
            if citation.snapshot_id != unit.snapshot_id:
                return self._reject("snapshot_mismatch", draft)
            if citation.response_start < 0 or citation.response_end > len(body):
                return self._reject("response_offset", draft)
            if citation.response_start >= citation.response_end:
                return self._reject("response_offset", draft)
            # Native documents include the source heading. Legacy providers may
            # cite the original answer body; both must quote actual source text.
            sources = [
                redact_for_model(document_body(unit)),
                redact_for_model(unit.answer_verbatim),
            ]
            if not any(
                0 <= citation.source_start < citation.source_end <= len(source)
                for source in sources
            ):
                return self._reject("source_offset", draft)
            if not any(
                citation.cited_text == source[citation.source_start : citation.source_end]
                for source in sources
            ):
                return self._reject("source_text_mismatch", draft)
            if citation.source_url != unit.source_url:
                return self._reject("source_metadata_mismatch", draft)
            cited_parts.append(citation.cited_text)

        body, citations = _trim_uncited_edges(body, citations)
        body, citations = _drop_uncited_spans(body, citations)
        if not body:
            return self._reject("empty", draft)
        if len(body) > _MAX_CHARS:
            return self._reject("over_length", draft)
        if len(body.split()) > _SOFT_WORD_CAP:
            return self._reject("over_words", draft)
        if _is_disallowed_source_copy(body, units, citations):
            return self._reject("source_copy", draft)
        clarifying = _is_clarifying_only(body)

        cited_text = "\n".join(cited_parts)

        if not clarifying:
            covered = 0
            gaps: list[str] = []
            for citation in sorted(citations, key=lambda item: item.response_start):
                if citation.response_start > covered:
                    gaps.append(body[covered : citation.response_start])
                covered = max(covered, citation.response_end)
            gaps.append(body[covered:])
            for gap in gaps:
                text = gap.strip()
                if not re.search(r"\w", text):
                    continue
                if _is_keepable_gap(text):
                    continue
                return self._reject("uncited_response_text", draft)

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
