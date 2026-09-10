from __future__ import annotations

from lxml.etree import _Element

from app.services.kb_extract.text import locator_for, tidy_text
from app.services.kb_extract.types import EvidenceUnit


def parse_accordions(tree: _Element, url: str) -> list[EvidenceUnit]:
    units: list[EvidenceUnit] = []
    units.extend(_aria_pairs(tree, url))
    units.extend(_details_pairs(tree, url))
    return units


def _aria_pairs(tree: _Element, url: str) -> list[EvidenceUnit]:
    units: list[EvidenceUnit] = []
    for button in tree.xpath("//button[@aria-controls]"):
        target_id = (button.get("aria-controls") or "").strip()
        if not target_id:
            continue
        try:
            region = tree.get_element_by_id(target_id)
        except KeyError:
            continue
        question = tidy_text(button.text_content())
        answer = tidy_text(region.text_content())
        if not question or not answer:
            continue
        units.append(
            EvidenceUnit(
                kind="faq",
                heading=question,
                canonical_question=question,
                answer_verbatim=answer,
                body_for_search=f"{question}\n{answer}",
                display_locator=locator_for(url, question),
            )
        )
    return units


def _details_pairs(tree: _Element, url: str) -> list[EvidenceUnit]:
    units: list[EvidenceUnit] = []
    for details in tree.xpath("//details"):
        summary = details.find("summary")
        if summary is None:
            continue
        question = tidy_text(summary.text_content())
        summary_text = summary.text_content()
        full = details.text_content()
        answer = tidy_text(full[len(summary_text) :] if full.startswith(summary_text) else full)
        if not question or not answer:
            continue
        units.append(
            EvidenceUnit(
                kind="faq",
                heading=question,
                canonical_question=question,
                answer_verbatim=answer,
                body_for_search=f"{question}\n{answer}",
                display_locator=locator_for(url, question),
            )
        )
    return units
