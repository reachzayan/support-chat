"""Local chrome strip for website ingest when Haiku is not used."""

from __future__ import annotations

import re
from dataclasses import replace

from app.llm.safety_markers import INJECTION_MARKERS, contains_injection_marker
from app.services.kb_alias import INJECTION_MARKERS as ALIAS_MARKERS
from app.services.kb_extract.text import tidy_text
from app.services.kb_extract.types import EvidenceUnit
from app.settings import get_settings

CTA_LINE_RE = re.compile(
    r"^[•\-\*\d\.\)\s]*(view|learn more|get started|read more)\s*$",
    re.IGNORECASE,
)
STRAY_ORDINAL_RE = re.compile(r"^\s*0\s*$")
CHROME_BODIES = frozenset({"view", "learn more", "read more", "get started"})


def clean_section_local(_heading: str, section_text: str) -> str:
    kept: list[str] = []
    for line in tidy_text(section_text).splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append("")
            continue
        if CTA_LINE_RE.match(stripped) or STRAY_ORDINAL_RE.match(stripped):
            continue
        kept.append(line)
    return tidy_text("\n".join(kept))


def apply_cleaner(units: list[EvidenceUnit]) -> list[EvidenceUnit]:
    if not units:
        return []
    return [item for item in (_from_local(unit) for unit in units) if item is not None]


def default_llm_client():
    from app.services.kb_page_structure import HaikuPageStructurer

    if not get_settings().anthropic_api_key:
        raise RuntimeError("anthropic_key_required_for_kb_structuring")
    return HaikuPageStructurer()


def _unsafe(value: str) -> bool:
    lowered = value.casefold()
    markers = INJECTION_MARKERS + ALIAS_MARKERS
    return contains_injection_marker(value) or any(marker in lowered for marker in markers)


def _is_chrome_text(value: str) -> bool:
    body = " ".join(value.casefold().split())
    return not body or body in CHROME_BODIES


def _from_local(unit: EvidenceUnit) -> EvidenceUnit | None:
    cleaned = clean_section_local(unit.heading, unit.answer_verbatim)
    if _is_chrome_text(cleaned) or _unsafe(cleaned):
        return None
    return replace(
        unit,
        answer_verbatim=cleaned,
        body_for_search=f"{unit.canonical_question or unit.heading}\n{cleaned}",
    )
