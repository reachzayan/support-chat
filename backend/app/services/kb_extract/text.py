from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlparse

from lxml import html as lxml_html

from app.llm.safety_markers import strip_invisible

_DECORATIVE_RE = re.compile(
    "[\u2190-\u21ff\u27f0-\u27ff\u2900-\u297f\u2b00-\u2bff\u25b2-\u25c7\u2713-\u2718\u00ab\u00bb]"
)


def _normalize_chars(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = strip_invisible(normalized)
    normalized = normalized.replace("\u00a0", " ")
    normalized = normalized.replace("\u201c", '"').replace("\u201d", '"')
    normalized = normalized.replace("\u2018", "'").replace("\u2019", "'")
    normalized = normalized.replace("\u2013", "-")
    normalized = normalized.replace("\u2014", " - ")
    normalized = _DECORATIVE_RE.sub(" ", normalized)
    return re.sub(r"([.!?])([A-Z][a-z]+\b)", r"\1 \2", normalized)


def tidy_inline(value: str) -> str:
    return " ".join(_normalize_chars(value).split())


def tidy_text(value: str) -> str:
    lines = [" ".join(line.split()) for line in _normalize_chars(value).splitlines()]
    paragraphs: list[str] = []
    buffer: list[str] = []
    for line in lines:
        if line:
            buffer.append(line)
            continue
        if buffer:
            paragraphs.append("\n".join(buffer))
            buffer = []
    if buffer:
        paragraphs.append("\n".join(buffer))
    return "\n\n".join(paragraphs)


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


ANSWER_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.@+-][a-z0-9]+)*")


def answer_digest(value: str) -> str:
    return " ".join(ANSWER_TOKEN_RE.findall((value or "").casefold()))


def locator_for(url: str, name: str | None = None) -> str | None:
    fragment = urlparse(url).fragment
    if fragment:
        return f"#{fragment}"
    if name:
        return f"#faq-{slug(name)}"
    return None
