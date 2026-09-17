"""Visitor-facing citation grain: page URL, or the source home page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class VisitorCitation:
    url: str
    title: str


def home_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}/"


def visitor_citation_url(*, page_url: str, origin_urls: list[str], start_url: str) -> str:
    if len([url for url in origin_urls if url]) >= 2:
        return start_url
    return page_url


def collapse_visitor_citations(items: list[tuple[str, str, str]]) -> list[VisitorCitation]:
    grouped: dict[str, list[tuple[str, str]]] = {}
    order: list[str] = []
    for page_url, title, start_url in items:
        key = start_url or page_url
        if key not in grouped:
            order.append(key)
            grouped[key] = []
        grouped[key].append((page_url, title))
    chips: list[VisitorCitation] = []
    for start_url in order:
        pages = grouped[start_url]
        unique_urls = list(dict.fromkeys(url for url, _title in pages))
        if len(unique_urls) == 1:
            url = unique_urls[0]
            title = next(title for page_url, title in pages if page_url == url)
            chips.append(VisitorCitation(url=url, title=title))
            continue
        host = urlparse(start_url).netloc
        chips.append(VisitorCitation(url=start_url, title=host))
    return chips


def visitor_citation_chips(items: list[tuple[str, str]]) -> list[VisitorCitation]:
    return collapse_visitor_citations(
        [(url, title, home_url(url)) for url, title in items if url or title]
    )


def visitor_citation_payloads(
    *,
    citations: list[Any] | None = None,
    source_urls: list[str] | None = None,
    source_title: str | None = None,
) -> list[dict[str, str | None]]:
    pairs: list[tuple[str, str]] = []
    for citation in citations or []:
        url = str(getattr(citation, "source_url", "") or "")
        title = str(getattr(citation, "source_title", "") or "")
        if url or title:
            pairs.append((url, title))
    if not pairs:
        for url in source_urls or []:
            pairs.append((url, source_title or ""))
    return [
        {"source_url": chip.url, "source_title": chip.title, "cited_text": None}
        for chip in visitor_citation_chips(pairs)
    ]
