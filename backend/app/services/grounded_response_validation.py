"""Validate grounded drafts against live evidence before they become chat rows."""
# ruff: noqa: RUF001

from __future__ import annotations

import re
from dataclasses import replace

import structlog

from app.llm.prompts import document_body
from app.llm.safety_markers import OUTPUT_PII_PATTERNS
from app.services import output_validator
from app.services.faq_fastpath import is_marketing_cta
from app.services.grounded_response_types import (
    Citation,
    DraftValidation,
    EvidenceUnit,
    ModelDraft,
    TurnContext,
)
from app.services.pii_redactor import redact_evidence
from app.settings import get_settings

log = structlog.get_logger("grounded_response")


_NUMERIC_CLAIM_RE = re.compile(
    r"\$\d+(?:\.\d{1,2})?|\b\d+(?:[-–]\d+)?\s*"
    r"(?:hours?|days?|minutes?|business days?)|\b\d+(?:\.\d+)?%",
    re.I,
)
_REGULATED_RE = re.compile(r"\b(?:DOT|USDOT|FMCSA|FCRA|HIPAA|49\s+CFR\s+Part\s+40)\b", re.I)
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


_UNPERFORMED_BOOKING_RE = re.compile(
    r"^(?:I (?:have not|haven't|haven’t) (?:booked|reserved|scheduled) (?:an|any) appointment"
    r"(?: for you)?(?: yet)?"
    r"|No he (?:reservado|programado) (?:ninguna|una) cita(?: para usted)?)[.!]?$",
    re.I,
)

# Mentioning a guarantee in a limitation or a request to ask about one is
# not an affirmative business promise. Other commitment terms stay literal.
_NON_ASSERTED_GUARANTEE_RE = re.compile(
    r"(?:\b(?:i|we) (?:cannot|can't|do not|don't) confirm\b[^,;.!?]{0,90}"
    r"|\b(?:ask|inquire|enquire) about\b[^,;.!?]{0,50})$",
    re.I,
)


_COMMITMENT_RE = re.compile(
    r"\b(?:free|guarantee(?:d)?|unlimited|certified|accredited|licensed"
    r"|at no (?:additional |extra )?(?:cost|charge))\b",
    re.I,
)
_FREE_IDIOM_BEFORE_RE = re.compile(
    r"(?:\bfeel\s+|\byou(?:['’]re|\s+are)\s+|\b(?!fee|cost|charge)\w+-)$", re.I
)


def _is_free_idiom(text: str, match: re.Match[str]) -> bool:
    """'Feel free', 'you are free to', 'toll-free', 'drug-free' say nothing about price.

    'Services are free to employers' stays a price claim.
    """
    return bool(_FREE_IDIOM_BEFORE_RE.search(text[: match.start()]))


def sentence_spans(body: str) -> list[re.Match[str]]:
    return list(re.finditer(r"\S.*?(?:[.!?](?=\s|$)|$)", body, re.S))


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
        or _UNPERFORMED_BOOKING_RE.fullmatch(stripped)
    )


def uncited_factual_sentences(draft: ModelDraft) -> list[str]:
    """The same sentence coverage used for validation and actionable repair feedback."""
    return [
        sentence.group().strip()
        for sentence in sentence_spans(draft.body.strip())
        if not _is_keepable_gap(sentence.group())
        and not any(
            citation.response_start < sentence.end() and citation.response_end > sentence.start()
            for citation in draft.citations
        )
    ]


def remove_draft_sentences(draft: ModelDraft, selected: list[str]) -> ModelDraft | None:
    """Delete only whole, exact sentences and remap retained citation offsets.

    Selection is untrusted model data: it can remove text, never add claims or
    evidence. Callers must validate and reassess the remaining answer.
    """
    spans = sentence_spans(draft.body)
    removals = {text.strip() for text in selected}
    if not removals or not removals.issubset({span.group().strip() for span in spans}):
        return None
    parts, citations, length = [], [], 0
    for span in spans:
        if span.group().strip() in removals:
            continue
        separator = " " if parts else ""
        offset = length + len(separator) - span.start()
        parts.append(separator + span.group())
        length += len(parts[-1])
        citations.extend(
            replace(
                citation,
                response_start=max(citation.response_start, span.start()) + offset,
                response_end=min(citation.response_end, span.end()) + offset,
            )
            for citation in draft.citations
            if citation.response_start < span.end() and citation.response_end > span.start()
        )
    body = "".join(parts)
    return ModelDraft(body, citations, draft.request_id) if body.strip() else None


def attribute_contact_literals(draft: ModelDraft, units: list[EvidenceUnit]) -> ModelDraft:
    """Attribute omitted contact literals only when they exactly occur in evidence.

    This supports only the literal email/phone, not surrounding claims about
    booking, availability, or callbacks. Full validation and semantic review
    still apply to the answer.
    """
    citations = list(draft.citations)
    for pattern in OUTPUT_PII_PATTERNS[-2:]:
        for match in pattern.finditer(draft.body):
            contact = match.group()
            if any(
                item.response_start <= match.start()
                and item.response_end >= match.end()
                and contact in item.cited_text
                for item in citations
            ):
                continue
            for unit in units:
                source = redact_evidence(document_body(unit))
                start = source.find(contact)
                if start < 0:
                    continue
                citations.append(
                    Citation(
                        unit.id,
                        unit.snapshot_id,
                        match.start(),
                        match.end(),
                        start,
                        start + len(contact),
                        contact,
                        unit.source_title,
                        unit.source_url,
                    )
                )
                break
    return ModelDraft(draft.body, citations, draft.request_id)


def focus_unknown_contact(draft: ModelDraft, units: list[EvidenceUnit]) -> ModelDraft:
    """Keep a leading honest limitation and one verified route, without sales filler.

    This narrow failure path adds no company claims: the limitation remains model
    authored and the contact must occur literally in both the draft and evidence.
    The returned draft still needs normal validation and semantic assessment.
    """
    sentences = sentence_spans(draft.body)
    if not sentences:
        return draft
    limitation = sentences[0].group().strip()
    if not _LIMITATION_RE.search(limitation) or not re.match(
        r"^(?:I |We |No puedo |No podemos )", limitation, re.I
    ):
        return draft
    sources = [redact_evidence(document_body(unit)) for unit in units]
    matches = sorted(
        (match for pattern in OUTPUT_PII_PATTERNS[-2:] for match in pattern.finditer(draft.body)),
        key=lambda match: match.start(),
    )
    for match in matches:
        contact = match.group()
        if any(contact in source for source in sources):
            route = (
                f"Puede contactarnos en {contact}."
                if limitation.casefold().startswith("no ")
                else f"You can contact us at {contact}."
            )
            return attribute_contact_literals(
                ModelDraft(f"{limitation}\n\n{route}", [], draft.request_id), units
            )
    return draft


def validate_draft(  # noqa: C901
    draft: ModelDraft,
    units: list[EvidenceUnit],
    turn: TurnContext,
) -> DraftValidation:
    body = draft.body.strip()
    citations = list(draft.citations)
    if not body:
        return _reject("empty", draft)
    if is_marketing_cta(body):
        return _reject("non_actionable_cta", draft)

    allowed = {unit.id: unit for unit in units}
    cited_parts: list[str] = []
    for citation in citations:
        unit = allowed.get(citation.chunk_id)
        if unit is None:
            return _reject("cite_off_corpus", draft)
        if citation.snapshot_id != unit.snapshot_id:
            return _reject("snapshot_mismatch", draft)
        if citation.response_start < 0 or citation.response_end > len(body):
            return _reject("response_offset", draft)
        if citation.response_start >= citation.response_end:
            return _reject("response_offset", draft)
        # Native documents include the source heading. Legacy providers may
        # cite the original answer body; both must quote actual source text.
        sources = [
            redact_evidence(document_body(unit)),
            redact_evidence(unit.answer_verbatim),
        ]
        if not any(
            0 <= citation.source_start < citation.source_end <= len(source) for source in sources
        ):
            return _reject("source_offset", draft)
        if not any(
            citation.cited_text == source[citation.source_start : citation.source_end]
            for source in sources
        ):
            return _reject("source_text_mismatch", draft)
        if citation.source_url != unit.source_url:
            return _reject("source_metadata_mismatch", draft)
        cited_parts.append(citation.cited_text)

    # Length is bounded by characters only; word counts are not a safe proxy
    # (Spanish and cited contact detail run long).
    max_chars = get_settings().max_bot_answer_chars
    if len(body) > max_chars:
        return _reject("over_length", draft)
    if _is_disallowed_source_copy(body, units, citations):
        return _reject("source_copy", draft)
    clarifying = _is_clarifying_only(body)
    visitor_recap = _is_visitor_recap(body, turn.prior_messages)

    cited_text = "\n".join(cited_parts)

    if not clarifying and not visitor_recap:
        if uncited_factual_sentences(draft):
            return _reject("uncited_response_text", draft)
        for sentence in sentence_spans(body):
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
            for match in _COMMITMENT_RE.finditer(text):
                term = " ".join(match.group().casefold().split())
                if term == "free" and _is_free_idiom(text, match):
                    continue
                if term.startswith("guarantee") and _NON_ASSERTED_GUARANTEE_RE.search(
                    text[: match.start()]
                ):
                    continue
                if not re.search(rf"\b{re.escape(term)}\b", " ".join(proof.split())):
                    return _reject("unsupported_commitment", draft)

    # Inability to confirm a requested percentage or regulation is not a
    # numeric promise or regulatory claim. Apply literal backing to the
    # same factual sentences that require citations, not to gap guidance.
    factual_text = "\n".join(
        sentence.group()
        for sentence in sentence_spans(body)
        if not _is_keepable_gap(sentence.group())
    )
    if not _numbers_are_verbatim(factual_text, cited_text):
        return _reject("unsupported_numeric", draft)
    if not _regulated_literals_are_verbatim(factual_text, cited_text):
        return _reject("unsupported_regulated", draft)

    safety = output_validator.evaluate(
        body,
        allowed_ids=[unit.id for unit in units],
        cited=[citation.chunk_id for citation in citations],
        citation_urls=[citation.source_url for citation in citations],
        live_urls={unit.source_url for unit in units if unit.source_url},
        cited_answer_text=cited_text,
        off_brand_blocklist=list(turn.off_brand_blocklist),
        max_chars=max_chars,
        curated_refusal=clarifying
        or visitor_recap
        or (
            not citations
            and (
                bool(_LIMITATION_RE.search(body))
                or (
                    any(
                        _UNPERFORMED_BOOKING_RE.fullmatch(s.group().strip())
                        for s in sentence_spans(body)
                    )
                    and all(_is_keepable_gap(s.group()) for s in sentence_spans(body))
                )
            )
        ),
        public_contact_text=cited_text,
    )
    if not safety.accepted:
        return _reject(safety.reason, draft)

    return DraftValidation(
        accepted=True,
        reason="accepted",
        draft=ModelDraft(body=body, citations=citations, request_id=draft.request_id),
    )


def _reject(reason: str, draft: ModelDraft) -> DraftValidation:
    log.info(
        "grounded_draft_reject",
        reason=reason,
        citation_count=len(draft.citations),
        body_chars=len(draft.body or ""),
    )
    return DraftValidation(accepted=False, reason=reason)
