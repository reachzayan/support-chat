from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlparse

from lxml import html as lxml_html

from app.llm.safety_markers import strip_invisible


def tidy_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = strip_invisible(normalized)
    lines = [re.sub(r" {2,}", " ", line).rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip()


def strip_html_text(value: str) -> str:
    if "<" not in value:
        return tidy_text(value)
    fragment = lxml_html.fragment_fromstring(value, create_parent=True)
    return tidy_text(fragment.text_content())


def visible_copy(html: str) -> str:
    if not html or not html.strip():
        return ""
    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        return strip_html_text(html)
    for tag in tree.xpath("//script|//style|//noscript"):
        parent = tag.getparent()
        if parent is not None:
            parent.remove(tag)
    return tidy_text(tree.text_content())


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:80]


def answer_hash(value: str) -> str:
    normalized = " ".join(value.split()).casefold()
    return hashlib.sha256(normalized.encode()).hexdigest()


def locator_for(url: str, name: str | None = None) -> str | None:
    fragment = urlparse(url).fragment
    if fragment:
        return f"#{fragment}"
    if name:
        return f"#faq-{slug(name)}"
    return None
