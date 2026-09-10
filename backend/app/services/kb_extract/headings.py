from __future__ import annotations

from lxml.etree import _Element

from app.services.kb_extract.text import locator_for, tidy_text
from app.services.kb_extract.types import EvidenceUnit

HEADING_LEVEL = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
SKIP_TAGS = {"nav", "footer", "header", "script", "style", "form", "noscript", "iframe"}


def parse_headings(tree: _Element, url: str) -> list[EvidenceUnit]:
    root = tree.find(".//main")
    if root is None:
        root = tree.find(".//article")
    if root is None:
        root = tree.find(".//body")
    if root is None:
        return []
    units: list[EvidenceUnit] = []
    headings = [
        node
        for node in root.iter()
        if isinstance(node.tag, str) and node.tag in HEADING_LEVEL and not _inside_skip(node)
    ]
    for index, heading in enumerate(headings):
        level = HEADING_LEVEL[heading.tag]
        title = tidy_text(heading.text_content())
        if not title:
            continue
        stop = None
        for nxt in headings[index + 1 :]:
            if HEADING_LEVEL[nxt.tag] <= level:
                stop = nxt
                break
        body = _collect_until(heading, stop)
        if not body:
            continue
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
    return units


def _inside_skip(node: _Element) -> bool:
    parent = node.getparent()
    while parent is not None:
        if isinstance(parent.tag, str) and parent.tag in SKIP_TAGS:
            return True
        if parent.get("role") == "navigation":
            return True
        parent = parent.getparent()
    return False


def _collect_until(heading: _Element, stop: _Element | None) -> str:
    parts: list[str] = []
    node = heading.getnext()
    while node is not None and node is not stop:
        if isinstance(node.tag, str) and node.tag in HEADING_LEVEL:
            break
        if isinstance(node.tag, str) and node.tag in SKIP_TAGS:
            node = node.getnext()
            continue
        if isinstance(node.tag, str) and node.tag in {"ul", "ol"}:
            for item in node.xpath("./li"):
                text = tidy_text(item.text_content())
                if text:
                    parts.append(f"- {text}")
        else:
            text = tidy_text(node.text_content()) if hasattr(node, "text_content") else ""
            if text:
                parts.append(text)
        node = node.getnext()
    return "\n\n".join(parts)
