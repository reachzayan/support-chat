from __future__ import annotations

from lxml.etree import _Element

from app.services.kb_extract.text import locator_for, tidy_text
from app.services.kb_extract.types import EvidenceUnit

HEADING_LEVEL = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
SKIP_TAGS = {"nav", "footer", "script", "style", "form", "noscript", "iframe"}


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
    seen_lists: set[int] = set()
    heading_tail = tidy_text(heading.tail or "")
    if heading_tail:
        parts.append(heading_tail)
    for node in heading.xpath("./following::*"):
        if stop is not None and node is stop:
            break
        if isinstance(node.tag, str) and node.tag in HEADING_LEVEL:
            break
        chunk = _chunk_for_node(node, seen_lists)
        if chunk:
            parts.append(chunk)
        tail = _tail_outside_chrome(node)
        if tail:
            parts.append(tail)
    return "\n\n".join(parts)


def _tail_outside_chrome(node: _Element) -> str | None:
    if _inside_skip(node):
        return None
    if isinstance(node.tag, str) and node.tag in SKIP_TAGS:
        return None
    return tidy_text(node.tail or "") or None


def _chunk_for_node(node: _Element, seen_lists: set[int]) -> str | None:
    if not isinstance(node.tag, str) or node.tag in SKIP_TAGS or _inside_skip(node):
        return None
    if node.tag in {"ul", "ol"}:
        identity = id(node)
        if identity in seen_lists:
            return None
        seen_lists.add(identity)
        items = [tidy_text(item.text_content()) for item in node.xpath("./li")]
        return "\n".join(f"- {text}" for text in items if text) or None
    if node.tag == "li":
        return None
    return tidy_text(node.text or "") or None
