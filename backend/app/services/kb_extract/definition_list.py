from __future__ import annotations

from lxml.etree import _Element

from app.services.kb_extract.text import locator_for, tidy_inline, tidy_text
from app.services.kb_extract.types import EvidenceUnit


def parse_definition_lists(tree: _Element, url: str) -> list[EvidenceUnit]:
    units: list[EvidenceUnit] = []
    for dl in tree.xpath("//dl"):
        children = [child for child in list(dl) if child.tag in {"dt", "dd"}]
        index = 0
        while index < len(children) - 1:
            dt = children[index]
            dd = children[index + 1]
            if dt.tag != "dt" or dd.tag != "dd":
                index += 1
                continue
            question = tidy_inline(dt.text_content())
            answer = tidy_text(dd.text_content())
            index += 2
            if not question or not answer:
                continue
            units.append(
                EvidenceUnit(
                    kind="definition",
                    heading=question,
                    canonical_question=question,
                    answer_verbatim=answer,
                    body_for_search=f"{question}\n{answer}",
                    display_locator=locator_for(url, question),
                )
            )
    return units
