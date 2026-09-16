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
MIN_CHARS = 40


def extract_html(html: str, url: str = "", markdown: str = "") -> list[EvidenceUnit]:
    try:
        tree = lxml_html.fromstring(html) if html else None
    except Exception:
        tree = None
    collected: list[EvidenceUnit] = []
    try:
        collected.extend(parse_faqpage(html, url))
    except Exception:
        log.info("kb_extract_skip", parser="jsonld")
    if tree is not None:
        try:
            collected.extend(parse_accordions(tree, url))
        except Exception:
            log.info("kb_extract_skip", parser="accordion")
        collected.extend(parse_definition_lists(tree, url))
        collected.extend(parse_headings(tree, url))
    collected.extend(parse_markdown(markdown, url))
    collected.extend(parse_fallback(html, url))
    return _dedupe(collected)


def _dedupe(units: list[EvidenceUnit]) -> list[EvidenceUnit]:
    seen: set[str] = set()
    seen_questions: set[str] = set()
    unique: list[EvidenceUnit] = []
    for unit in units:
        if not unit.answer_verbatim:
            continue
        if unit.canonical_question:
            question = " ".join(unit.canonical_question.casefold().split())
            if question in seen_questions:
                continue
            seen_questions.add(question)
        if unit.kind == "prose" and len(unit.answer_verbatim) < MIN_CHARS:
            continue
        if unit.kind == "prose":
            uncovered = _uncovered_prose(unit.answer_verbatim, unique)
            if len(uncovered) < MIN_CHARS:
                continue
            unit = replace(
                unit,
                answer_verbatim=uncovered,
                body_for_search=f"{unit.heading}\n{uncovered}",
            )
        digest = answer_hash(unit.answer_verbatim)
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(unit)
    return unique


def _uncovered_prose(block: str, unique: list[EvidenceUnit]) -> str:
    remainder = block
    for item in unique:
        if item.kind == "prose":
            continue
        if remainder in item.answer_verbatim:
            return ""
        remainder = remainder.replace(item.answer_verbatim, " ")
    return " ".join(remainder.split())
