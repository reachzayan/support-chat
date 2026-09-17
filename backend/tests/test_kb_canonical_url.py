from app.services.kb_ingest import canonical_fetch_url, display_locator


def test_canonical_fetch_url_strips_fragment_port_and_lowercases_host() -> None:
    assert canonical_fetch_url("https://sample-site.example.com:443/#faq") == "https://sample-site.example.com/"
    assert canonical_fetch_url("https://sample-site.example.com") == "https://sample-site.example.com/"
    assert (
        canonical_fetch_url("https://sample-site.example.com/faq#timing")
        == "https://sample-site.example.com/faq"
    )


def test_display_locator_keeps_fragment() -> None:
    assert display_locator("https://sample-site.example.com/#faq") == "#faq"
    assert display_locator("https://sample-site.example.com/faq") is None


def test_canonical_fetch_url_upgrades_http_to_https() -> None:
    assert canonical_fetch_url("http://sample-site.example.com/faq") == "https://sample-site.example.com/faq"
