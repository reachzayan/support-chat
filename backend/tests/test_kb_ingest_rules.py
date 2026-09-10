from app.services.kb_ingest import path_depth, path_matches_globs, path_under_prefix


def test_path_under_prefix_requires_segment_boundary() -> None:
    start = "https://sample-site.example.com/foo"
    assert path_under_prefix("https://sample-site.example.com/foo", start) is True
    assert path_under_prefix("https://sample-site.example.com/foo/bar", start) is True
    assert path_under_prefix("https://sample-site.example.com/foobar", start) is False


def test_path_depth_counts_segments_after_prefix() -> None:
    start = "https://sample-site.example.com/docs"
    assert path_depth("https://sample-site.example.com/docs", start) == 0
    assert path_depth("https://sample-site.example.com/docs/guide", start) == 1
    assert path_depth("https://sample-site.example.com/docs/guide/page", start) == 2


def test_include_glob_requires_match_when_configured() -> None:
    assert path_matches_globs("/faq", ["/faq*"], []) is True
    assert path_matches_globs("/dot", ["/faq*"], []) is False


def test_exclude_glob_blocks_matching_paths() -> None:
    assert path_matches_globs("/admin/settings", [], ["/admin*"]) is False
    assert path_matches_globs("/faq", [], ["/admin*"]) is True
