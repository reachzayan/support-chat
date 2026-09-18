"""Select original source blocks; omit chrome and interactive example outputs."""

from __future__ import annotations

import re
from html import escape, unescape
from urllib.parse import unquote, urlparse

from lxml import html

_BLOCKS = {"p", "li", "dl", "table", "blockquote", "pre", "address"}
_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6", "summary"}
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\+?\(?\d[\d(). -]{7,}\d")
_SYNTAX_SPAN = re.compile(
    r"(<span\b(?=[^>]*punctuation)[^>]*>)(.*?)(</span>)",
    re.IGNORECASE | re.DOTALL,
)
_CLOSING_QUOTES = "\"'\u201d\u2019\u00bb)]}"


def _text(node) -> str:
    return " ".join(node.text_content().split())


def _prose(text: str) -> bool:
    return len(text.split()) >= 5 or (len(text.split()) >= 3 and text.endswith((".", "!", "?")))


def _sentence(text: str) -> bool:
    return len(text.split()) >= 5 and text.rstrip(_CLOSING_QUOTES).endswith((".", "!", "?"))


def _compact_content_card(node) -> bool:
    """Accept CMS cards with prose in spans without accepting their outer grid."""
    direct_prose = any(child.tag == "span" and _sentence(_text(child)) for child in node)
    if not direct_prose:
        return False
    for child in node:
        if child.tag == "span":
            continue
        if child.tag == "div":
            text_length = len(_text(child))
            link_length = sum(len(_text(link)) for link in child.xpath(".//a"))
            if text_length and link_length / text_length >= 0.5:
                continue
        return False
    return True


def protect_code_punctuation(content: str) -> str:
    """Escape raw angle tokens emitted by syntax highlighters before HTML parsing."""

    def protect(match: re.Match[str]) -> str:
        opening, value, closing = match.groups()
        if not any(char in value for char in "<>"):
            return match.group()
        return f"{opening}{escape(unescape(value), quote=False)}{closing}"

    return _SYNTAX_SPAN.sub(protect, content)


def _compact_card_html(node) -> str:
    parts = []
    for child in node:
        if child.tag != "span":
            continue
        text = _text(child)
        if text and text not in parts:
            parts.append(text)
    return f"<p>{'<br>'.join(escape(part) for part in parts)}</p>" if parts else ""


def _remove_interactive_outputs(tree) -> None:
    # A calculator's displayed defaults are not service facts. Retain its intro,
    # but exclude controls and the results following them. No hostname rules.
    controls = tree.xpath('//input | //select | //textarea | //*[@role="slider"]')
    regions = set()
    for control in controls:
        region = next(
            (parent for parent in control.iterancestors() if parent.tag in {"section", "form"}),
            control.getparent(),
        )
        regions.add(region)
    for region in regions:
        if sum(control in region.iterdescendants() for control in controls) < 2:
            # A single quantity/search field is not evidence of a calculator.
            continue
        intro = []
        for node in region.iter():
            if node in controls:
                break
            if node.tag in _HEADINGS | {"p"}:
                intro.append(html.tostring(node, encoding="unicode", with_tail=False))
        region.clear()
        region.tag = "div"
        for fragment in intro:
            region.append(html.fromstring(fragment))


def _question(node) -> bool:
    eligible = node.tag in _HEADINGS | {"button"} or node.get("role") == "button"
    if not eligible:
        eligible = node.tag == "div" and not node.xpath(".//a | .//div | .//p | .//button")
    return eligible and _text(node).endswith("?")


def _faq_regions(tree) -> set:
    regions = set(tree.iter("details"))
    by_id = {node.get("id"): node for node in tree.iter() if node.get("id")}
    for node in tree.iter():
        if not _question(node):
            continue
        target = by_id.get(node.get("aria-controls"))
        if target is None:
            target = node.getnext()
        if target is not None and target.tag in {"div", "section", "p"} and not _question(target):
            regions.add(target)
    return regions


def _in_region(node, regions: set) -> bool:
    return node in regions or any(parent in regions for parent in node.iterancestors())


def _candidate(node, faq_regions: set) -> bool:
    tag = node.tag
    if tag in _BLOCKS | _HEADINGS:
        return not (
            tag == "li"
            and any(child.tag in _BLOCKS | _HEADINGS for child in node.iterdescendants())
        )
    if tag == "a":
        return node.get("href", "").startswith(("mailto:", "tel:"))
    if tag == "button":
        return _text(node).endswith("?")
    if _question(node):
        return True
    # Some CMSes use divs for paragraphs and accordion answers.
    if tag != "div":
        return False
    leaf_container = not any(
        child.tag in _BLOCKS | _HEADINGS | {"div", "section", "button"}
        for child in node.iterdescendants()
    )
    return (
        leaf_container
        and (
            (len(_text(node).split()) >= 8 and _text(node).endswith((".", "!", "?")))
            or _in_region(node, faq_regions)
        )
    ) or _compact_content_card(node)


def _contact_html(node, text: str) -> str:
    if node.get("href", "").startswith("mailto:"):
        address = unquote(urlparse(node.get("href")).path)
        if not _EMAIL.fullmatch(address) or address not in text:
            return ""
        text = address
    elif match := _PHONE.search(text):
        text = match.group()
    return f"<p>{escape(text)}</p>"


def _block_html(node, text: str, faq_regions: set) -> str:
    tag = node.tag
    if tag == "a":
        return _contact_html(node, text)
    if tag in _HEADINGS | {"button"} or _question(node):
        heading_tag = tag if tag.startswith("h") else "h3"
        return f"<{heading_tag}>{escape(text)}</{heading_tag}>"
    if tag == "dl":
        pairs = []
        for term in node.xpath(".//dt"):
            values = term.xpath("following-sibling::dd[1]")
            if values:
                label = " ".join(" ".join(values[0].itertext()).split())
                pairs.append(f"<p>{escape(_text(term))} {escape(label)}</p>")
        return "\n".join(pairs)
    if tag == "li":
        return f"<ul><li>{escape(text)}</li></ul>" if len(text.split()) >= 2 else ""
    if tag == "div" and _compact_content_card(node):
        return _compact_card_html(node)
    if tag in {"p", "div"}:
        faq_answer = _in_region(node, faq_regions) and (
            text.endswith((".", "!", "?")) or text.casefold() in {"yes", "no"}
        )
        return f"<p>{escape(text)}</p>" if _prose(text) or faq_answer else ""
    return html.tostring(node, encoding="unicode", with_tail=False)


def knowledge_html(content: str) -> str:
    if not content.strip():
        return ""
    tree = html.fromstring(protect_code_punctuation(content))
    _remove_interactive_outputs(tree)
    for br in tree.iter("br"):
        br.tail = " " + (br.tail or "")
    faq_regions = _faq_regions(tree)
    accepted, contacts = [], []
    main_regions = tree.xpath(
        '//main | //*[@role="main"] | '
        '//*[contains(concat(" ", normalize-space(@class), " "), " main-content ")]'
    )
    represented = set()
    seen = set()
    heading = ""
    for node in tree.iter():
        if not _candidate(node, faq_regions) or any(
            parent in represented for parent in node.iterancestors()
        ):
            continue
        if (
            main_regions
            and node.tag not in {"a", "address"}
            and not any(node == main or main in node.iterancestors() for main in main_regions)
        ):
            continue
        text = _text(node)
        block = _block_html(node, text, faq_regions)
        if not text or not block:
            continue
        footer = any(parent.tag == "footer" for parent in node.iterancestors())
        if footer and node.tag not in {"a", "address"}:
            continue
        if node.tag in _HEADINGS | {"button"} or _question(node):
            heading = text
            accepted.append(block)
            represented.add(node)
            continue
        key = ("" if node.tag == "a" else heading, node.tag, block)
        if key in seen:
            continue
        seen.add(key)
        represented.add(node)
        (contacts if footer else accepted).append(block)
    return "\n".join(contacts + accepted)
