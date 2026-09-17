from __future__ import annotations

import trafilatura
from lxml import html as lxml_html

from app.services.kb_extract.text import locator_for, tidy_text
from app.services.kb_extract.types import EvidenceUnit

DROP_TAGS = (
    "script",
    "style",
    "nav",
    "footer",
    "noscript",
    "iframe",
    "svg",
    "form",
)


def _html_without_chrome(html: str) -> str:
    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        return html
    _strip_noise_nodes(tree)
    return lxml_html.tostring(tree, encoding="unicode")


def parse_fallback(html: str, url: str, markdown: str = "") -> list[EvidenceUnit]:
    cleaned_html = _html_without_chrome(html)
    title = _title(cleaned_html)
    if markdown.strip() and not any(
        line.lstrip().startswith("#") for line in markdown.splitlines()
    ):
        return _blocks_from_text(tidy_text(markdown), title or "Untitled", url)
    text = trafilatura.extract(
        cleaned_html, include_comments=False, include_tables=True, favor_recall=True
    )
    if text is None:
        text, title = _fallback_dom(cleaned_html)
    if text is None:
        return []
    return _blocks_from_text(tidy_text(text), title or "Untitled", url)


def _blocks_from_text(text: str, heading: str, url: str) -> list[EvidenceUnit]:
    blocks = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not blocks and text:
        blocks = [text]
    return [
        EvidenceUnit(
            kind="prose",
            heading=heading,
            canonical_question=None,
            answer_verbatim=block,
            body_for_search=f"{heading}\n{block}",
            display_locator=locator_for(url),
        )
        for block in blocks
    ]


def _title(html: str) -> str:
    metadata = trafilatura.extract_metadata(html)
    if metadata is not None and metadata.title:
        return metadata.title.strip()
    return ""


def _strip_noise_nodes(tree) -> None:
    for tag in DROP_TAGS:
        for node in tree.findall(f".//{tag}"):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    for nav in tree.xpath("//*[@role='navigation']"):
        parent = nav.getparent()
        if parent is not None:
            parent.remove(nav)


def _dom_title(tree) -> str:
    h1 = tree.find(".//h1")
    if h1 is not None and h1.text_content():
        return h1.text_content().strip()
    title_el = tree.find(".//title")
    if title_el is not None:
        return (title_el.text or "").strip()
    return ""


def _dom_content_root(tree):
    for selector in (".//main", ".//article", ".//body"):
        root = tree.find(selector)
        if root is not None:
            return root
    return None


def _fallback_dom(html: str) -> tuple[str | None, str]:
    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        return None, ""
    _strip_noise_nodes(tree)
    title = _dom_title(tree)
    root = _dom_content_root(tree)
    if root is None:
        return None, title
    return root.text_content(), title
