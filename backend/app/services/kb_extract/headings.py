from __future__ import annotations

import re

from lxml.etree import _Element

from app.services.kb_extract.text import locator_for, tidy_inline, tidy_text
from app.services.kb_extract.types import EvidenceUnit

HEADING_LEVEL = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
HEADING_CLASS_RE = re.compile(r"(?:^|\s)(?:heading|title|section-title)(?:\s|$)", re.I)
SKIP_TAGS = {
    "nav",
    "footer",
    "script",
    "style",
    "form",
    "noscript",
    "iframe",
    "svg",
    "details",
    "dl",
}
TABLE_INNER = {"tr", "td", "th", "thead", "tbody", "tfoot"}


def parse_headings(tree: _Element, url: str) -> list[EvidenceUnit]:
    # An article can be a single product card, not the page's content root.
    root = tree if tree.tag == "body" else tree.find(".//body")
    if root is None:
        root = tree
    units: list[EvidenceUnit] = []
    headings = [
        node for node in root.iter() if _heading_level(node) is not None and not _inside_skip(node)
    ]
    for index, heading in enumerate(headings):
        level = _heading_level(heading) or 2
        title = tidy_inline(_node_text(heading))
        if not title:
            continue
        stop = None
        for nxt in headings[index + 1 :]:
            nxt_level = _heading_level(nxt) or 2
            if nxt_level <= level:
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


def _heading_level(node: _Element) -> int | None:
    if not isinstance(node.tag, str):
        return None
    if node.tag in HEADING_LEVEL:
        return HEADING_LEVEL[node.tag]
    if node.get("role") == "heading":
        try:
            return max(1, min(6, int(node.get("aria-level") or 2)))
        except ValueError:
            return 2
    if HEADING_CLASS_RE.search(node.get("class") or ""):
        return 2
    return None


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
    seen_blocks: set[_Element] = set()
    heading_tail = tidy_text(heading.tail or "")
    if heading_tail:
        parts.append(heading_tail)
    for node in heading.xpath("./following::*"):
        if stop is not None and node is stop:
            break
        if _heading_level(node) is not None:
            break
        chunk = _chunk_for_node(node, seen_blocks)
        if chunk:
            parts.append(chunk)
        tail = (
            None
            if any(parent in seen_blocks for parent in node.iterancestors())
            else _tail_outside_chrome(node)
        )
        if tail:
            parts.append(tail)
    return "\n\n".join(parts)


def _tail_outside_chrome(node: _Element) -> str | None:
    if _inside_skip(node):
        return None
    if isinstance(node.tag, str) and node.tag in SKIP_TAGS:
        return None
    return tidy_text(node.tail or "") or None


def _chunk_for_node(node: _Element, seen_blocks: set[_Element]) -> str | None:
    if not isinstance(node.tag, str) or node.tag in SKIP_TAGS or _inside_skip(node):
        return None
    if any(parent in seen_blocks for parent in node.iterancestors()):
        return None
    if node.tag in {"ul", "ol"}:
        return _list_chunk(node, seen_blocks)
    if node.tag == "table":
        return _table_chunk(node, seen_blocks)
    if node.tag in {"li", *TABLE_INNER}:
        return None
    if node.tag in {"p", "blockquote"}:
        seen_blocks.add(node)
        return tidy_text(_node_text(node)) or None
    if node.tag in {"div", "span", "a"} and not node.xpath(
        ".//div|.//p|.//ul|.//ol|.//table|.//h1|.//h2|.//h3|.//h4|.//h5|.//h6"
    ):
        seen_blocks.add(node)
        return tidy_text(_node_text(node)) or None
    return tidy_text(node.text or "") or None


def _list_chunk(node: _Element, seen_blocks: set[_Element]) -> str | None:
    if node in seen_blocks:
        return None
    seen_blocks.add(node)
    items = [tidy_inline(_node_text(item)) for item in node.xpath("./li")]
    return "\n".join(f"- {text}" for text in items if text) or None


def _table_chunk(node: _Element, seen_blocks: set[_Element]) -> str | None:
    if node in seen_blocks:
        return None
    seen_blocks.add(node)
    rows: list[str] = []
    for row in node.xpath(".//tr"):
        cells = [tidy_inline(cell.text_content()) for cell in row.xpath("./th|./td")]
        line = " | ".join(cell for cell in cells if cell)
        if line:
            rows.append(line)
    return "\n".join(rows) or None


def _node_text(node: _Element) -> str:
    parts = [node.text or ""]
    for child in node:
        if isinstance(child.tag, str) and child.tag not in SKIP_TAGS:
            parts.append("\n" if child.tag == "br" else _node_text(child))
        parts.append(child.tail or "")
    separator = (
        " "
        if node.tag == "div" and re.search(r"\b(?:flex|grid)\b", node.get("class") or "")
        else ""
    )
    return separator.join(parts)
