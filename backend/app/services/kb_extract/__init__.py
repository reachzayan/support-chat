from __future__ import annotations

from dataclasses import replace

import structlog
from lxml import html as lxml_html

from app.services.kb_extract.accordion import parse_accordions
from app.services.kb_extract.definition_list import parse_definition_lists
from app.services.kb_extract.fallback import parse_fallback
from app.services.kb_extract.headings import parse_headings
from app.services.kb_extract.jsonld import parse_faqpage
from app.services.kb_extract.markdown import parse_markdown
from app.services.kb_extract.text import answer_hash
from app.services.kb_extract.types import EvidenceUnit

log = structlog.get_logger("kb_extract")
WEAK_SECTION_BODIES = {"view", "learn more", "read more", "get started"}


def extract_html(html: str, url: str = "", markdown: str = "") -> list[EvidenceUnit]:
    try:
        tree = lxml_html.fromstring(html) if html else None
    except Exception:
        tree = None
    collected: list[EvidenceUnit] = []
    if tree is not None:
        try:
            collected.extend(parse_accordions(tree, url))
        except Exception:
            log.info("kb_extract_skip", parser="accordion")
        collected.extend(parse_definition_lists(tree, url))
        collected.extend(parse_headings(tree, url))
    try:
        collected.extend(parse_faqpage(html, url))
    except Exception:
        log.info("kb_extract_skip", parser="jsonld")
    had_html_units = bool(collected)
    heading_sections = any(unit.kind in {"section", "table"} for unit in collected)
    if not collected:
        collected.extend(parse_markdown(markdown, url))
        heading_sections = any(unit.kind in {"section", "table"} for unit in collected)
    if not heading_sections:
        collected.extend(parse_fallback(html, url, markdown="" if had_html_units else markdown))
    return _dedupe(collected)


def _dedupe(units: list[EvidenceUnit]) -> list[EvidenceUnit]:
    seen: dict[str, int] = {}
    seen_questions: set[str] = set()
    unique: list[EvidenceUnit] = []
    for unit in units:
        if _skip_unit(unit):
            continue
        if unit.canonical_question:
            question = " ".join(unit.canonical_question.casefold().split())
            if question in seen_questions:
                continue
            seen_questions.add(question)
        digest = answer_hash(
            unit.answer_verbatim
            if unit.kind == "faq"
            else f"{unit.heading}\n{unit.answer_verbatim}"
        )
        if digest in seen:
            existing_index = seen[digest]
            existing = unique[existing_index]
            if existing.kind == "faq" and unit.kind == "faq":
                unique[existing_index] = _merge_faq_alias(existing, unit)
            elif _prefer_structured(unit, existing):
                unique[existing_index] = unit
            continue
        seen[digest] = len(unique)
        unique.append(unit)
    return unique


def _skip_unit(unit: EvidenceUnit) -> bool:
    if not unit.answer_verbatim:
        return True
    body = " ".join(unit.answer_verbatim.casefold().split())
    if body in WEAK_SECTION_BODIES:
        return True
    heading = " ".join(unit.heading.casefold().split())
    lines = [
        " ".join(line.casefold().split())
        for line in unit.answer_verbatim.splitlines()
        if line.strip()
    ]
    return bool(lines) and all(line in WEAK_SECTION_BODIES or line == heading for line in lines)


def _prefer_structured(candidate: EvidenceUnit, existing: EvidenceUnit) -> bool:
    structured = {"faq", "definition"}
    return candidate.kind in structured and existing.kind not in structured


def _merge_faq_alias(existing: EvidenceUnit, duplicate: EvidenceUnit) -> EvidenceUnit:
    alias = duplicate.canonical_question
    if not alias or alias == existing.canonical_question or alias in existing.aliases:
        return existing
    return replace(existing, aliases=(*existing.aliases, alias))
