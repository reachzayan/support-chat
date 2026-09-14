"""Typed, evidence-first decisions for visitor-facing bot replies.

This module intentionally owns the only server-authored non-factual copy.  A
provider may contribute a cited answer, but it cannot turn a question into a
clarification or a policy response.
"""
# ruff: noqa: RUF001

from __future__ import annotations

import re
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

import structlog

from app.chat.outcome_copy import TECH_FAIL_HUMAN
from app.llm.intent import is_disengage_request, is_unrelated_request
from app.llm.safety_markers import contains_injection_marker
from app.services import output_validator
from app.services.kb_tokens import WEAK_OVERLAP, tokenize
from app.services.pii_redactor import redact_for_model

log = structlog.get_logger("grounded_response")


class ResponseOutcome(StrEnum):
    EXACT_ANSWER = "exact_answer"
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


@dataclass(frozen=True)
class ModelDraft:
    body: str
    citations: list[Citation]


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
_VERBATIM_RISKS = frozenset({"credential", "pricing", "timing", "legal"})
_MAX_CHARS = 1500
_SOFT_WORD_CAP = 120


def technical_failure_decision() -> ResponseDecision:
    return ResponseDecision(
        None,
        "tech_fail",
        TECH_FAIL_HUMAN,
        offer_handoff=True,
        provider_status=ProviderStatus.TECH_FAIL,
    )


def normalized_question(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    normalized = _PUNCT_RE.sub(" ", normalized)
    return " ".join(normalized.split())


def _eligible(units: list[EvidenceUnit]) -> list[EvidenceUnit]:
    return [
        unit for unit in units if unit.enabled and unit.live and unit.answer_mode != "human_only"
    ]


def _matches(unit: EvidenceUnit, question: str) -> bool:
    normalized = normalized_question(question)
    candidates = [unit.canonical_question or "", *unit.aliases]
    return normalized in {normalized_question(candidate) for candidate in candidates if candidate}


def _material_terms(question: str) -> set[str]:
    return {term for term in tokenize(question) if term not in WEAK_OVERLAP}


def _unit_terms(unit: EvidenceUnit) -> set[str]:
    return set(
        tokenize(
            " ".join(
                (
                    unit.canonical_question or "",
                    " ".join(unit.aliases),
                    unit.topic_label,
                    unit.answer_verbatim,
                )
            )
        )
    )


def _relevant(units: list[EvidenceUnit], question: str) -> list[EvidenceUnit]:
    query_terms = _material_terms(question)
    if not query_terms:
        # Overview / filler-only questions: keep retrieved units as-is.
        return list(units)[:5]
    scored: list[tuple[int, EvidenceUnit]] = []
    for unit in units:
        unit_terms = _unit_terms(unit)
        score = sum(1 for term in query_terms if term in unit_terms)
        if score:
            scored.append((score, unit))
    if scored:
        return [
            unit
            for _score, unit in sorted(scored, key=lambda pair: (-pair[0], str(pair[1].id)))[:5]
        ]
    return list(units)[:5]


def _coverage(units: list[EvidenceUnit], question: str) -> tuple[set[str], set[str]]:
    query_terms = _material_terms(question)
    if not query_terms:
        return set(), set()
    covered: set[str] = set()
    evidence_terms: set[str] = set()
    for unit in units:
        evidence_terms |= _unit_terms(unit)
    for term in query_terms:
        if term in evidence_terms:
            covered.add(term)
    return covered, query_terms - covered


def _topic_clusters(units: list[EvidenceUnit]) -> list[str]:
    labels = list(dict.fromkeys(unit.topic_label for unit in units if unit.topic_label))
    return labels


def _missing_concept(question: str, missing: set[str]) -> str:
    """Build a readable unsupported-concept phrase from the visitor's words."""
    raw = (question or "").strip()
    lowered = raw.casefold()
    if missing & {"registered", "registration"} and "registered with" in lowered:
        match = re.search(
            r"(?:are\s+you\s+|whether\s+(?:you\s+are\s+)?)?(registered with \w+)",
            raw,
            re.I,
        )
        if match:
            return f"whether you are {match.group(1)}"
    if " and " in lowered:
        for clause in re.split(r"\band\b", raw, flags=re.I):
            clause_terms = set(tokenize(clause))
            if clause_terms & missing:
                cleaned = " ".join(clause.strip().rstrip("?").split())
                if cleaned:
                    return cleaned
    return ", ".join(sorted(missing)[:3]) or "that detail"


def _capabilities(context: TurnContext) -> list[str]:
    labels = list(context.site_capability_labels) or [unit.topic_label for unit in context.evidence]
    return list(dict.fromkeys(label for label in labels if label))[:3]


def _citation(unit: EvidenceUnit, *, response_start: int, response_end: int) -> Citation:
    return Citation(
        chunk_id=unit.id,
        snapshot_id=unit.snapshot_id,
        response_start=response_start,
        response_end=response_end,
        source_start=0,
        source_end=len(unit.answer_verbatim),
        cited_text=unit.answer_verbatim,
        source_title=unit.source_title,
        source_url=unit.source_url,
    )


def extractive_fallback_decision(units: list[EvidenceUnit]) -> ResponseDecision:
    bodies: list[str] = []
    citations: list[Citation] = []
    offset = 0
    for index, unit in enumerate(units):
        text = unit.answer_verbatim.strip()
        if not text:
            continue
        if index and bodies:
            offset += 2  # blank line separator
        start = offset
        end = start + len(text)
        bodies.append(text)
        citations.append(_citation(unit, response_start=start, response_end=end))
        offset = end
    if not bodies:
        return technical_failure_decision()
    return ResponseDecision(
        ResponseOutcome.SYNTHESIZED_ANSWER,
        "extractive_fallback",
        "\n\n".join(bodies),
        citations=citations,
        provider_status=ProviderStatus.TECH_FAIL,
    )


def _document_for_citation(unit: EvidenceUnit) -> str:
    return redact_for_model(unit.answer_verbatim)


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


def _strip_trailing_question(body: str) -> str | None:
    text = body.strip()
    if "?" not in text:
        return text
    # Prefer a factual prefix before the first question mark sentence.
    parts = re.split(r"(?<=[.!])\s+(?=[A-Z])", text)
    kept: list[str] = []
    for part in parts:
        if "?" in part:
            break
        kept.append(part)
    prefix = " ".join(kept).strip()
    return prefix or None


class GroundedResponseEngine:
    def __init__(self, complete: Provider | None = None) -> None:
        self._complete = complete

    async def respond(self, turn: TurnContext) -> ResponseDecision:  # noqa: C901
        question = (turn.visitor_text or "").strip()
        if turn.sensitive:
            return ResponseDecision(
                ResponseOutcome.BOUNDARY,
                "policy_sensitive",
                "For privacy and compliance, a specialist needs to help with that question.",
                offer_handoff=True,
            )
        if turn.explicit_human_request:
            return ResponseDecision(
                ResponseOutcome.BOUNDARY,
                "visitor_request",
                "",
                offer_handoff=True,
            )
        if _ABUSE_RE.search(question):
            return self._boundary("abuse")
        if contains_injection_marker(question) or is_disengage_request(question):
            return self._boundary("prompt_injection")
        if _FRUSTRATION_RE.search(question):
            return self._boundary("frustration")
        evidence_tokens: set[str] = set()
        for unit in turn.evidence:
            evidence_tokens |= _unit_terms(unit)
        # Off-topic only when retrieval found no site affinity. Retrieved units mean
        # the question stays in the answerability path (gap/partial/synth).
        if not turn.evidence and is_unrelated_request(question):
            return self._boundary("off_topic", turn)
        if turn.evidence and is_unrelated_request(
            question, evidence_tokens=evidence_tokens or None
        ):
            # Still block clear non-business prompts even if weak hits arrived.
            from app.services.kb_tokens import is_overview_query

            if not evidence_tokens & set(tokenize(question)) and not is_overview_query(question):
                # Credential / registration follow-ups with neighboring evidence are gaps,
                # not off-topic.
                if not set(tokenize(question)) & {
                    "usdot",
                    "registered",
                    "registration",
                    "dot",
                    "number",
                    "credential",
                }:
                    return self._boundary("off_topic", turn)

        units = _eligible(turn.evidence)
        exact = [unit for unit in units if _matches(unit, question)]
        if len(exact) == 1:
            unit = exact[0]
            body = unit.answer_verbatim.strip()
            return ResponseDecision(
                ResponseOutcome.EXACT_ANSWER,
                None,
                body,
                citations=[_citation(unit, response_start=0, response_end=len(body))],
            )

        relevant = _relevant(units, question)
        all_clusters = _topic_clusters(turn.evidence)
        clusters = _topic_clusters(relevant) or all_clusters
        if self._needs_clarification(
            question, all_clusters if len(all_clusters) >= 2 else clusters, turn
        ):
            labels = (all_clusters if len(all_clusters) >= 2 else clusters)[:3]
            if len(labels) < 2:
                labels = list(turn.site_capability_labels)[:3] or ["screening services"]
            return ResponseDecision(
                ResponseOutcome.CLARIFICATION,
                "ambiguous_topic",
                f"Are you asking about {' or '.join(labels)}?",
            )

        covered, missing = _coverage(relevant, question)
        from app.services.kb_tokens import is_overview_query

        if is_overview_query(question) and relevant:
            covered, missing = set(tokenize(question)), set()
        # Registration/credential asks with no supporting eligible unit are gaps,
        # even when a human_only unit exists in the corpus.
        if missing and not covered:
            return self._gap(turn)
        if missing and covered:
            supported = [unit for unit in relevant if _unit_terms(unit) & covered] or relevant[:1]
            return await self._partial(turn, supported, missing)
        if missing and not covered:
            return self._gap(turn)
        if not relevant:
            return self._gap(turn)
        if self._complete is None:
            return extractive_fallback_decision(relevant[:5])
        try:
            draft = await self._complete(turn, relevant[:5])
        except Exception:
            return extractive_fallback_decision(relevant[:5])
        if draft is None:
            return extractive_fallback_decision(relevant[:5])
        validation = self._validate_draft(draft, relevant, turn)
        if not validation.accepted or validation.draft is None:
            return extractive_fallback_decision(relevant[:5])
        return ResponseDecision(
            ResponseOutcome.SYNTHESIZED_ANSWER,
            None,
            validation.draft.body,
            citations=validation.draft.citations,
            provider_status=ProviderStatus.OK,
        )

    async def _partial(
        self,
        turn: TurnContext,
        supported: list[EvidenceUnit],
        missing: set[str],
    ) -> ResponseDecision:
        missing_label = _missing_concept(turn.visitor_text, missing)
        limitation = (
            f"I can’t verify {missing_label} from the available site information. "
            "Would you like a specialist to confirm it?"
        )
        factual = ""
        citations: list[Citation] = []
        if self._complete is not None:
            try:
                draft = await self._complete(turn, supported[:5])
            except Exception:
                draft = None
            if draft is not None:
                validation = self._validate_draft(draft, supported, turn)
                if validation.accepted and validation.draft is not None:
                    factual = validation.draft.body.strip()
                    citations = list(validation.draft.citations)
        if not factual:
            extractive = extractive_fallback_decision(supported)
            if not extractive.citations:
                return self._gap(turn)
            factual = extractive.body
            citations = extractive.citations
            # Citations cover only the factual portion.
            for index, citation in enumerate(citations):
                if citation.response_end > len(factual):
                    citations[index] = Citation(
                        chunk_id=citation.chunk_id,
                        snapshot_id=citation.snapshot_id,
                        response_start=min(citation.response_start, len(factual)),
                        response_end=min(citation.response_end, len(factual)),
                        source_start=citation.source_start,
                        source_end=citation.source_end,
                        cited_text=citation.cited_text,
                        source_title=citation.source_title,
                        source_url=citation.source_url,
                    )
        body = f"{factual}\n\n{limitation}"
        return ResponseDecision(
            ResponseOutcome.PARTIAL_ANSWER,
            "partial_coverage",
            body,
            citations=citations,
            offer_handoff=True,
            provider_status=ProviderStatus.OK if citations else ProviderStatus.TECH_FAIL,
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
        if "?" in body:
            stripped = _strip_trailing_question(body)
            if stripped is None:
                return self._reject("model_question", draft)
            # Keep citations that still fall inside the stripped prefix.
            kept = [
                citation
                for citation in citations
                if 0 <= citation.response_start < citation.response_end <= len(stripped)
            ]
            body = stripped
            citations = kept
            draft = ModelDraft(body=body, citations=citations)
        if not citations:
            return self._reject("no_citation", draft)

        allowed = {unit.id: unit for unit in units}
        cited_text = ""
        for citation in citations:
            unit = allowed.get(citation.chunk_id)
            if unit is None:
                return self._reject("cite_off_corpus", draft)
            if citation.snapshot_id != unit.snapshot_id:
                return self._reject("snapshot_mismatch", draft)
            if citation.source_title != unit.source_title or citation.source_url != unit.source_url:
                return self._reject("metadata_mismatch", draft)
            source = _document_for_citation(unit)
            if citation.source_start < 0 or citation.source_end > len(source):
                return self._reject("source_offset", draft)
            if citation.cited_text != source[citation.source_start : citation.source_end]:
                return self._reject("cited_text_mismatch", draft)
            if citation.response_start < 0 or citation.response_end > len(body):
                return self._reject("response_offset", draft)
            requires_verbatim = (
                unit.answer_mode == "verbatim_only" or unit.risk_class in _VERBATIM_RISKS
            )
            if requires_verbatim and (
                body[citation.response_start : citation.response_end] != citation.cited_text
            ):
                return self._reject("verbatim_required", draft)
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
        )
        if not safety.accepted:
            return self._reject(safety.reason, draft)

        return DraftValidation(
            accepted=True, reason="accepted", draft=ModelDraft(body=body, citations=citations)
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
    def _needs_clarification(
        question: str,
        clusters: list[str],
        turn: TurnContext,
    ) -> bool:
        del turn
        from app.services.kb_tokens import is_overview_query

        if len(clusters) < 2:
            return False
        if is_overview_query(question):
            return False
        terms = set(tokenize(question))
        if not terms:
            return False
        # Parent-concept questions that do not name a single topic (e.g. registration).
        if terms & {"registered", "registration", "usdot"}:
            return True
        scored = sorted((len(terms & set(tokenize(label))), label) for label in clusters)
        scored.reverse()
        if scored[0][0] <= 0:
            return False
        # Ambiguous when the top two topic labels share the same overlap score.
        return scored[0][0] == scored[1][0]

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
                "I can help with screening and compliance questions using site information. "
                "What would you like to know?"
            )
        else:
            labels = _capabilities(turn) if turn is not None else []
            topic = ", ".join(labels) if labels else "screening and compliance"
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

    @staticmethod
    def _gap(turn: TurnContext) -> ResponseDecision:
        labels = _capabilities(turn)
        capabilities = ", ".join(labels) if labels else "screening and compliance services"
        return ResponseDecision(
            ResponseOutcome.KNOWLEDGE_GAP,
            "no_evidence",
            "I don’t have verified information for that specific question. "
            f"I can help with {capabilities}, or connect you with a specialist.",
            offer_handoff=True,
        )
