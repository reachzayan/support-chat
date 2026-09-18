from __future__ import annotations

import re

from app.services.kb_extract.text import locator_for, tidy_inline, tidy_text
from app.services.kb_extract.types import EvidenceUnit


def parse_markdown(markdown: str, url: str) -> list[EvidenceUnit]:
    if not markdown or not markdown.strip():
        return []
    units: list[EvidenceUnit] = []
    heading = ""
    parts: list[str] = []
    fence = ""
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        marker = re.match(r"^(`{3,}|~{3,})", line)
        if marker:
            value = marker.group()
            if not fence:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = ""
            parts.append(raw_line)
            continue
        match = re.match(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", line) if not fence else None
        if match:
            _flush(units, heading, parts, url)
            heading = match.group(1)
            parts = []
            continue
        parts.append(raw_line)
    _flush(units, heading, parts, url)
    return units


def _flush(units: list[EvidenceUnit], heading: str, parts: list[str], url: str) -> None:
    source = "\n".join(parts)
    has_code = any(line.lstrip().startswith(("```", "~~~")) for line in parts)
    body = source.strip() if has_code else tidy_text(source)
    title = tidy_inline(heading) or "Untitled"
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
