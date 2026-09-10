from __future__ import annotations

import json
from typing import Any

from app.services.kb_extract.text import locator_for, strip_html_text, tidy_text
from app.services.kb_extract.types import EvidenceUnit


def parse_faqpage(html: str, url: str) -> list[EvidenceUnit]:
    from lxml import html as lxml_html

    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        return []
    units: list[EvidenceUnit] = []
    for script in tree.xpath("//script[@type='application/ld+json']"):
        raw = script.text or ""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        units.extend(_walk(payload, url))
    return units


def _walk(payload: Any, url: str) -> list[EvidenceUnit]:
    units: list[EvidenceUnit] = []
    if isinstance(payload, list):
        for item in payload:
            units.extend(_walk(item, url))
        return units
    if not isinstance(payload, dict):
        return units
    if "@graph" in payload:
        units.extend(_walk(payload["@graph"], url))
    types = payload.get("@type")
    type_names = types if isinstance(types, list) else [types]
    names = {str(item) for item in type_names if item}
    if "FAQPage" in names:
        units.extend(_walk(payload.get("mainEntity"), url))
    if "Question" in names:
        unit = _question_unit(payload, url)
        if unit is not None:
            units.append(unit)
    return units


def _question_unit(payload: dict, url: str) -> EvidenceUnit | None:
    name = tidy_text(str(payload.get("name") or payload.get("text") or ""))
    answer = payload.get("acceptedAnswer") or payload.get("suggestedAnswer") or {}
    if isinstance(answer, list) and answer:
        answer = answer[0]
    if not isinstance(answer, dict):
        return None
    text = strip_html_text(str(answer.get("text") or ""))
    if not name or not text:
        return None
    locator = locator_for(url, name)
    return EvidenceUnit(
        kind="faq",
        heading=name,
        canonical_question=name,
        answer_verbatim=text,
        body_for_search=f"{name}\n{text}",
        display_locator=locator,
    )
