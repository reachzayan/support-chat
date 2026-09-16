from __future__ import annotations

from app.services.kb_extract.text import locator_for, tidy_text
from app.services.kb_extract.types import EvidenceUnit


def parse_markdown(markdown: str, url: str) -> list[EvidenceUnit]:
    if not markdown or not markdown.strip():
        return []
    units: list[EvidenceUnit] = []
    heading = ""
    parts: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            _flush(units, heading, parts, url)
            heading = line.lstrip("#").strip()
            parts = []
            continue
        parts.append(raw_line)
    _flush(units, heading, parts, url)
    return units


def _flush(units: list[EvidenceUnit], heading: str, parts: list[str], url: str) -> None:
    body = tidy_text("\n".join(parts))
    title = tidy_text(heading) or "Untitled"
    if not body:
        return
    units.append(
        EvidenceUnit(
            kind="section",
            heading=title,
            canonical_question=None,
            answer_verbatim=body,
            body_for_search=f"{title}\n{body}",
            display_locator=locator_for(url, title),
        )
    )
