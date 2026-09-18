from app.chat.display_citations import collapse_visitor_citations, visitor_citation_url


def test_one_page_citation_stays_on_that_page() -> None:
    chips = collapse_visitor_citations(
        [
            (
                "https://sample-data.example.com/samplemail",
                "SampleMail",
                "https://sample-data.example.com/",
            )
        ]
    )
    assert [(chip.url, chip.title) for chip in chips] == [
        ("https://sample-data.example.com/samplemail", "SampleMail")
    ]


def test_two_pages_in_the_same_source_collapse_to_the_home_page() -> None:
    chips = collapse_visitor_citations(
        [
            (
                "https://sample-data.example.com/samplemail",
                "SampleMail",
                "https://sample-data.example.com/",
            ),
            (
                "https://sample-data.example.com/collections",
                "Collections",
                "https://sample-data.example.com/",
            ),
        ]
    )
    assert [(chip.url, chip.title) for chip in chips] == [
        ("https://sample-data.example.com/", "sample-data.example.com")
    ]


def test_shared_answer_cites_the_source_home_page() -> None:
    url = visitor_citation_url(
        page_url="https://sample-data.example.com/",
        origin_urls=[
            "https://sample-data.example.com/",
            "https://sample-data.example.com/samplemail",
            "https://sample-data.example.com/collections",
        ],
        start_url="https://sample-data.example.com/",
    )
    assert url == "https://sample-data.example.com/"


def test_page_local_answer_cites_that_page() -> None:
    url = visitor_citation_url(
        page_url="https://sample-data.example.com/samplemail",
        origin_urls=[],
        start_url="https://sample-data.example.com/",
    )
    assert url == "https://sample-data.example.com/samplemail"
