from app.services.kb_crawl import parse_sitemap_locs, sitemap_urls_from_robots

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://sample-site.example.com/faq</loc></url>
  <url><loc>https://sample-site.example.com/dot</loc></url>
  <url><loc>http://sample-site.example.com/insecure</loc></url>
</urlset>
"""

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://sample-site.example.com/sitemap-pages.xml</loc></sitemap>
</sitemapindex>
"""


def test_parse_sitemap_locs_keeps_https_only() -> None:
    urls = parse_sitemap_locs(SITEMAP)
    assert urls == [
        "https://sample-site.example.com/faq",
        "https://sample-site.example.com/dot",
    ]


def test_parse_sitemap_index_returns_nested_sitemap_urls() -> None:
    urls = parse_sitemap_locs(INDEX)
    assert urls == ["https://sample-site.example.com/sitemap-pages.xml"]


def test_robots_sitemap_directive_is_collected() -> None:
    body = "User-agent: *\nDisallow: /admin\nSitemap: https://sample-site.example.com/sitemap.xml\n"
    assert sitemap_urls_from_robots(body) == ["https://sample-site.example.com/sitemap.xml"]
