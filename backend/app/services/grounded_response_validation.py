"""Validate grounded drafts against live evidence before they become chat rows."""
# ruff: noqa: RUF001

from __future__ import annotations

import re

import structlog

from app.llm.prompts import document_body
from app.services import output_validator
from app.services.grounded_response_types import (
    Citation,
    DraftValidation,
    EvidenceUnit,
    ModelDraft,
    TurnContext,
)
from app.services.pii_redactor import redact_evidence

log = structlog.get_logger("grounded_response")


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


def validate_draft(  # noqa: C901
    draft: ModelDraft,
    units: list[EvidenceUnit],
    turn: TurnContext,
) -> DraftValidation:
    body = draft.body.strip()
    citations = list(draft.citations)
    if not body:
        return _reject("empty", draft)

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

    if len(body) > _MAX_CHARS:
        return _reject("over_length", draft)
    if len(body.split()) > _SOFT_WORD_CAP:
        return _reject("over_words", draft)
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
            for term in re.findall(
                r"\b(?:free|guarantee(?:d)?|unlimited|certified|accredited|licensed)\b",
                text,
                re.I,
            ):
                if not re.search(rf"\b{re.escape(term.casefold())}\b", proof):
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
        max_chars=_MAX_CHARS,
        curated_refusal=clarifying
        or visitor_recap
        or (not citations and bool(_LIMITATION_RE.search(body))),
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
