"""Discover and filter sitemap URLs within the configured site boundary."""

from __future__ import annotations

from urllib.parse import urlparse

from app.models.kb_source import KbSource
from app.models.site import Site
from app.services.kb_crawl import (
    parse_sitemap_locs,
    sitemap_urls_from_robots,
)


async def _planned_urls(source: KbSource, site: Site, hosts: set[str], fetch, robots) -> list[str]:
    from app.services.kb_ingest import _plan_urls

    if source.mode == "prefix":
        sitemap_urls = await _sitemap_seed_urls(source, site, hosts, fetch, robots)
        if sitemap_urls:
            return sitemap_urls[: source.max_pages]
    return _plan_urls(source)[: source.max_pages]


async def _sitemap_seed_urls(
    source: KbSource, site: Site, hosts: set[str], fetch, robots
) -> list[str]:
    from app.services.kb_ingest import robots_body

    host = urlparse(source.start_url).hostname
    candidates: list[str] = []
    robots_txt = await robots_body(source.start_url, hosts, fetch, robots) or ""
    candidates.extend(sitemap_urls_from_robots(robots_txt))
    if host:
        candidates.append(f"https://{host.casefold()}/sitemap.xml")
        candidates.append(f"https://{host.casefold()}/sitemap_index.xml")
    locs = await _expand_sitemap_locs(candidates, hosts, fetch)
    return _filter_sitemap_urls(locs, source, site)


async def _expand_sitemap_locs(candidates: list[str], hosts: set[str], fetch) -> list[str]:
    from app.services.kb_ingest import try_fetch

    locs: list[str] = []
    nested: list[str] = []
    seen: set[str] = set()
    for sitemap_url in candidates:
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        body = await try_fetch(sitemap_url, hosts, fetch)
        if not body:
            continue
        parsed = parse_sitemap_locs(body)
        if not parsed:
            continue
        for loc in parsed:
            if loc.rstrip("/").endswith(".xml"):
                nested.append(loc)
            else:
                locs.append(loc)
    for sitemap_url in nested:
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        body = await try_fetch(sitemap_url, hosts, fetch)
        if body:
            locs.extend(parse_sitemap_locs(body))
    return locs


def _filter_sitemap_urls(locs: list[str], source: KbSource, site: Site) -> list[str]:
    from app.services.kb_ingest import (
        CanonicalError,
        _url_allowed_by_source_rules,
        canonical_fetch_url,
        host_allowed,
    )

    filtered: list[str] = []
    for loc in locs:
        try:
            url = canonical_fetch_url(loc)
        except CanonicalError:
            continue
        if not host_allowed(url, site, source.start_url):
            continue
        if not _url_allowed_by_source_rules(url, source):
            continue
        if url not in filtered:
            filtered.append(url)
    return filtered
