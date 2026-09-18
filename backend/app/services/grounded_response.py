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
    injection_boundary_line,
    transfer_offer_line,
)
from app.llm.intent import ABUSE_TOKENS, is_disengage_request
from app.llm.prompts import document_body
from app.llm.safety_markers import contains_injection_marker
from app.services import output_validator
from app.services.bot_trace import record_trace
from app.services.kb_tokens import tokenize
from app.services.pii_redactor import redact_evidence

log = structlog.get_logger("grounded_response")


class ResponseOutcome(StrEnum):
    EXACT_ANSWER = "exact_answer"  # Deprecated: no longer produced by respond().
    SYNTHESIZED_ANSWER = "synthesized_answer"
    CLARIFICATION = "clarification"
    PARTIAL_ANSWER = "partial_answer"
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
RepairProvider = Callable[
    [TurnContext, list[EvidenceUnit], ModelDraft], Awaitable[ModelDraft | None]
]

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
        "sí",
        "no",
        "and",
        "also",
        "including",
        "these include",
        "our services include",
        "specifically",
        "in particular",
        "here is how it works",
        "here's how it works",
        "you can also",
        "and we also work with",
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
_LIMITATION_RE = re.compile(
    r"^(?:(?:however|but|unfortunately),?\s+|to (?:discuss|confirm|understand) [^.!?]{1,140},\s+)?(?:"
    r"(?:i|we) (?:cannot|can't|can not|don't|do not|am unable to|are unable to) "
    r"(?:confirm|guarantee|verify|promise|provide|access|retrieve|determine|estimate)\b"
    r"|(?:a|our) specialist (?:can|needs to|must|would need to|will need to|should) "
    r"(?:confirm|verify|help|review|discuss|provide)\b"
    r"|(?:no puedo|no podemos) (?:confirmar|garantizar|verificar|determinar|proporcionar)\b"
    r"|(?:un|nuestro) especialista (?:debe|necesita|tiene que) "
    r"(?:confirmar|verificar|revisar|proporcionar)\b)",
    re.I,
)
_FOLLOWUP_RE = re.compile(r"\b(?:it|its|that|those|these|both|either|they|them)\b", re.I)
_GENERIC_FOLLOWUP_TERMS = frozenset(
    {
        "pricing",
        "price",
        "cost",
        "costs",
        "about",
        "turnaround",
        "timing",
        "result",
        "available",
        "availability",
        "standard",
        "setup",
        "start",
        "getting",
        "started",
        "yes",
        "no",
        "huh",
        "say",
        "said",
        "again",
        "mean",
        "means",
        "more",
        "details",
    }
)
_UNRELATED_TASK_RE = re.compile(
    r"\b(?:malware|ransomware|steal (?:passwords|credentials)|weather forecast|"
    r"write (?:a poem|a song)|recipe for|cook (?:pasta|a meal))\b",
    re.I,
)


def contextual_grounding_query(
    visitor_text: str,
    prior_messages: tuple[dict[str, str], ...],
    *,
    source_subject: str = "",
) -> str:
    """Add a bounded subject only for fragments or explicit references.

    Full, self-contained questions must not inherit an unrelated old answer.
    The provider receives the conversation separately from this search query.
    """
    if len(visitor_text.split()) > 6 and not _FOLLOWUP_RE.search(visitor_text):
        return visitor_text
    if (
        not _FOLLOWUP_RE.search(visitor_text)
        and set(tokenize(visitor_text)) - _GENERIC_FOLLOWUP_TERMS
    ):
        return visitor_text
    if source_subject:
        return f"{source_subject[:200]} {visitor_text}"
    for message in reversed(prior_messages):
        if message.get("role") != "assistant":
            continue
        body = (message.get("content") or "").strip()
        if body:
            # A missing-information reply is not a new product subject, though
            # a request to restate that reply still needs its actual wording.
            if _LIMITATION_RE.search(body) and visitor_text.strip().casefold() not in {
                "huh?",
                "huh",
            }:
                continue
            return f"{body[:160]} {visitor_text}"
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


def _is_visitor_recap(body: str, prior_messages: tuple[dict[str, str], ...]) -> bool:
    match = re.fullmatch(
        r'You (?:said|told me|originally said):\s*["“](.+)["”][.!]?', body.strip(), re.S | re.I
    )
    if not match:
        return False
    quote = " ".join(match.group(1).split())
    return any(
        quote in " ".join((message.get("content") or "").split())
        for message in prior_messages
        if message.get("role") == "user"
    )


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


def _is_keepable_gap(text: str) -> bool:
    stripped = (text or "").strip().lstrip(".!:;, ")
    if not re.search(r"\w", stripped):
        return True
    connective = " ".join(stripped.casefold().split()).strip(".!:;, ")
    if connective in _KEEPABLE_GAPS:
        return True
    return bool(
        _is_courtesy_edge(stripped)
        or _is_clarifying_only(stripped)
        or _LIMITATION_RE.search(stripped)
    )


def uncited_factual_sentences(draft: ModelDraft) -> list[str]:
    """The same sentence coverage used for validation and actionable repair feedback."""
    return [
        sentence.group().strip()
        for sentence in re.finditer(r"\S.*?(?:[.!?](?=\s|$)|$)", draft.body.strip(), re.S)
        if not _is_keepable_gap(sentence.group())
        and not any(
            citation.response_start < sentence.end() and citation.response_end > sentence.start()
            for citation in draft.citations
        )
    ]


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
    reason: str,
    *,
    prior_miss_count: int = 0,
    site_name: str = "",
    request_id: str | None = None,
) -> ResponseDecision:
    """Visitor-safe copy when the provider succeeded but draft validation failed.

    Specific reject reason is already on the grounded_draft_reject log line.
    """
    del reason, site_name
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
        validation = self._validate_draft(draft, evidence, turn)
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
                validation = self._validate_draft(draft, evidence, turn)
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
                reason=validation.reason,
                prior_miss_count=_same_kind_miss_count(turn, "grounding_reject"),
                site_name=turn.site_name,
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
            for sentence in re.finditer(r"\S.*?(?:[.!?](?=\s|$)|$)", validation.draft.body, re.S)
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
                redact_evidence(document_body(unit)),
                redact_evidence(unit.answer_verbatim),
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

        if not body:
            return self._reject("empty", draft)
        if len(body) > _MAX_CHARS:
            return self._reject("over_length", draft)
        if len(body.split()) > _SOFT_WORD_CAP:
            return self._reject("over_words", draft)
        if _is_disallowed_source_copy(body, units, citations):
            return self._reject("source_copy", draft)
        clarifying = _is_clarifying_only(body)
        visitor_recap = _is_visitor_recap(body, turn.prior_messages)

        cited_text = "\n".join(cited_parts)

        if not clarifying and not visitor_recap:
            if uncited_factual_sentences(draft):
                return self._reject("uncited_response_text", draft)
            for sentence in re.finditer(r"\S.*?(?:[.!?](?=\s|$)|$)", body, re.S):
                text = sentence.group().strip()
                if _is_keepable_gap(text):
                    continue
                attached = [
                    item
                    for item in citations
                    if item.response_start < sentence.end() and item.response_end > sentence.start()
                ]
                # Citation text blocks may cover a clause, but attribution is
                # at the sentence level. Commitments still need literal backing.
                proof = " ".join(item.cited_text.casefold() for item in attached)
                for term in re.findall(
                    r"\b(?:free|guarantee(?:d)?|unlimited|certified|accredited|licensed)\b",
                    text,
                    re.I,
                ):
                    if not re.search(rf"\b{re.escape(term.casefold())}\b", proof):
                        return self._reject("unsupported_commitment", draft)

        # Inability to confirm a requested percentage or regulation is not a
        # numeric promise or regulatory claim. Apply literal backing to the
        # same factual sentences that require citations, not to gap guidance.
        factual_text = "\n".join(
            sentence.group()
            for sentence in re.finditer(r"\S.*?(?:[.!?](?=\s|$)|$)", body, re.S)
            if not _is_keepable_gap(sentence.group())
        )
        if not _numbers_are_verbatim(factual_text, cited_text):
            return self._reject("unsupported_numeric", draft)
        if not _regulated_literals_are_verbatim(factual_text, cited_text):
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
            curated_refusal=clarifying
            or visitor_recap
            or (not citations and bool(_LIMITATION_RE.search(body))),
            public_contact_text=cited_text,
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
