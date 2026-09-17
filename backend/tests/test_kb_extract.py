from pathlib import Path

from app.services.kb_extract import extract_html
from app.services.kb_extract.text import tidy_inline, tidy_text

FIXTURE = Path(__file__).parent / "fixtures" / "kb" / "samplesite_timing.html"


def test_product_articles_do_not_limit_page_extraction_to_first_card() -> None:
    units = extract_html("""<html><body>
      <h1>Products</h1><p>Available for institutional users.</p>
      <article><h2>Addresses</h2><p>Current addresses.</p></article>
      <article><h2>Phones</h2><p>Multiple scored phone numbers.</p></article>
      <h2>Restrictions</h2><p>Not for employment decisions.</p>
    </body></html>""")
    sections = {unit.heading: unit.answer_verbatim for unit in units}
    assert sections["Products"] == "Available for institutional users."
    assert sections["Phones"] == "Multiple scored phone numbers."
    assert sections["Restrictions"] == "Not for employment decisions."


def test_inline_copy_and_list_items_are_read_once_with_heading_breaks() -> None:
    units = extract_html("""<html><body><main>
      <h2>One engine<br>Many platforms</h2>
      <p>We provide <strong>verified</strong> addresses.</p>
      <ul><li>Current <span>address</span></li><li>Prior addresses</li></ul>
    </main></body></html>""")
    assert units[0].heading == "One engine Many platforms"
    assert units[0].answer_verbatim == (
        "We provide verified addresses.\n\n- Current address\n- Prior addresses"
    )


def test_extract_keeps_turnaround_and_drops_nav() -> None:
    html = FIXTURE.read_text()
    units = extract_html(html, url="https://sample-site.example.com/faq")
    assert units
    answers = " ".join(unit.answer_verbatim for unit in units)
    assert "24-48 hours" in answers
    assert "Careers" not in answers


def test_extract_skips_empty_pages() -> None:
    units = extract_html("<html><body></body></html>", url="https://sample-site.example.com/faq")
    assert units == []


def test_short_compliance_fact_is_kept() -> None:
    html = """
    <html><head><title>Home</title></head><body>
      <p>FCRA-compliant</p>
      <p>Results in 24-48 hours</p>
    </body></html>
    """
    units = extract_html(html, url="https://sample-site.example.com/")
    answers = " ".join(unit.answer_verbatim for unit in units)
    assert "FCRA-compliant" in answers
    assert "24-48 hours" in answers


def test_definition_list_pairs_dt_with_dd() -> None:
    html = """
    <html><body>
    <dl>
      <dt>How quickly are drug screening results available?</dt>
      <dd>Most negative results are reported within 24-48 hours.</dd>
    </dl>
    </body></html>
    """
    units = extract_html(html, url="https://sample-site.example.com/glossary")
    definitions = [unit for unit in units if unit.kind == "definition"]
    assert len(definitions) == 1
    assert definitions[0].canonical_question == "How quickly are drug screening results available?"
    assert (
        definitions[0].answer_verbatim == "Most negative results are reported within 24-48 hours."
    )


def test_nested_heading_wrapper_keeps_section_body() -> None:
    html = """
    <html><body>
    <main>
      <section>
        <div><h2>Title</h2></div>
        <div><p>Body copy that must be indexed.</p></div>
      </section>
    </main>
    </body></html>
    """
    units = extract_html(html, url="https://example.com/services")
    sections = [unit for unit in units if unit.kind == "section"]
    title = next(unit for unit in sections if unit.heading == "Title")
    assert "Body copy that must be indexed." in title.answer_verbatim


def test_hero_in_header_is_kept_and_nav_is_dropped() -> None:
    html = """
    <html><body>
    <header>
      <nav><a href="/careers">Careers</a></nav>
      <h1>Employment screening</h1>
      <p>FCRA compliant sample services for employers.</p>
    </header>
    <footer>Privacy</footer>
    </body></html>
    """
    units = extract_html(html, url="https://example.com/")
    answers = " ".join(unit.answer_verbatim for unit in units)
    headings = " ".join(unit.heading for unit in units)
    assert "Employment screening" in headings
    assert "FCRA compliant sample services for employers." in answers
    assert "Careers" not in answers
    assert "Privacy" not in answers


def test_visible_faq_wins_over_near_duplicate_jsonld_answer() -> None:
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{
          "@type": "Question",
          "name": "What are collection solutions?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Collection solutions are data, verification, and contact tools."
          }
        }]
      }
      </script>
      <details>
        <summary>What are collection solutions?</summary>
        <p>Collection solutions are the data, verification, and contact tools.</p>
      </details>
    </body></html>
    """
    units = extract_html(html, url="https://sample-data.example.com/collections")
    faqs = [unit for unit in units if unit.canonical_question == "What are collection solutions?"]
    assert [unit.answer_verbatim for unit in faqs] == [
        "Collection solutions are the data, verification, and contact tools."
    ]


def test_html_evidence_prevents_markdown_chrome_from_becoming_an_untitled_section() -> None:
    html = """
    <html><body><main>
      <h2>Account verification</h2>
      <p>SampleMail verifies account ownership before payment.</p>
    </main></body></html>
    """
    markdown = "[Sample Data Services logo](/)\n\nNavigation\n\nView"

    units = extract_html(html, url="https://sample-data.example.com/samplemail", markdown=markdown)

    assert all(unit.heading != "Untitled" for unit in units)


def test_one_word_view_section_is_not_published_as_evidence() -> None:
    html = "<html><body><main><h2>Collection</h2><p>View</p></main></body></html>"

    units = extract_html(html, url="https://sample-data.example.com/")

    assert units == []


def test_fallback_keeps_unique_prose_next_to_structured_faq() -> None:
    html = """
    <html><head><title>Data services</title></head><body><main>
      <details>
        <summary>What is identity verification?</summary>
        <p>Identity verification checks submitted information against trusted records.</p>
      </details>
      <p>Our collection specialists also locate updated phone and address information.</p>
    </main></body></html>
    """
    units = extract_html(html, url="https://sample-data.example.com/collections")
    answers = "\n".join(unit.answer_verbatim for unit in units)
    assert (
        "Our collection specialists also locate updated phone and address information." in answers
    )


def test_headings_preserve_paragraph_breaks_and_list_bullets() -> None:
    html = """
    <html><body>
    <main>
      <h2>Turnaround</h2>
      <p>Most negative results are reported within 24-48 hours.</p>
      <p>Rapid negatives can arrive in minutes.</p>
      <ul><li>MRO review for non-negatives</li></ul>
      <h2>Pricing</h2>
      <p>Ask a specialist for a quote.</p>
    </main>
    </body></html>
    """
    units = extract_html(html, url="https://sample-site.example.com/faq")
    sections = [unit for unit in units if unit.kind == "section"]
    turnaround = next(unit for unit in sections if unit.heading == "Turnaround")
    assert "24-48 hours" in turnaround.answer_verbatim
    assert "\n" in turnaround.answer_verbatim
    assert "- MRO review for non-negatives" in turnaround.answer_verbatim
    assert "Ask a specialist for a quote." not in turnaround.answer_verbatim


def test_tidy_text_keeps_list_and_paragraph_breaks() -> None:
    cleaned = tidy_text(
        "Skip tracing\n\n- nationwide addresses\n- scored phones\n\nFCRA-compliant."
    )
    assert cleaned == ("Skip tracing\n\n- nationwide addresses\n- scored phones\n\nFCRA-compliant.")


def test_tidy_inline_collapses_heading_whitespace() -> None:
    assert tidy_inline("  One   data\nengine  ") == "One data engine"


def test_role_heading_extracts_skip_trace_section() -> None:
    html = """
    <html><body>
      <div role="heading" aria-level="2">Skip tracing</div>
      <p>Nationwide addresses, scored phones, and right-party contact.</p>
    </body></html>
    """
    units = extract_html(html, url="https://sample-data.example.com/collections")
    skip = next(unit for unit in units if unit.heading == "Skip tracing")
    assert "right-party contact" in skip.answer_verbatim


def test_section_title_class_and_h5_are_treated_as_headings() -> None:
    html = """
    <html><body>
      <div class="section-title">VPOE</div>
      <p>VPOE confirms employment dates from the payroll source.</p>
      <h5>eVPOE</h5>
      <p>eVPOE returns the same employment record electronically.</p>
    </body></html>
    """
    units = extract_html(html, url="https://sample-data.example.com/collections")
    headings = {unit.heading: unit.answer_verbatim for unit in units}
    assert "payroll source" in headings["VPOE"]
    assert "electronically" in headings["eVPOE"]


def test_heading_table_cells_stay_on_separate_lines() -> None:
    html = """
    <html><body><main>
      <h2>Mail pricing</h2>
      <table>
        <tr><th>Product</th><th>Rate</th></tr>
        <tr><td>First-class</td><td>$0.49</td></tr>
      </table>
    </main></body></html>
    """
    units = extract_html(html, url="https://sample-data.example.com/samplemail")
    pricing = next(unit for unit in units if unit.heading == "Mail pricing")
    assert "$0.49" in pricing.answer_verbatim
    assert "\n" in pricing.answer_verbatim


def test_markdown_headings_are_used_when_html_has_no_headings() -> None:
    html = "<html><body><div class='hero'>splash</div></body></html>"
    markdown = "## Skip tracing\n\nNationwide addresses, scored phones, and right-party contact."
    units = extract_html(html, url="https://sample-data.example.com/collections", markdown=markdown)
    skip = next(unit for unit in units if unit.heading == "Skip tracing")
    assert "right-party contact" in skip.answer_verbatim


def test_partial_faq_overlap_does_not_discard_skip_trace_prose() -> None:
    html = """
    <html><head><title>Collections</title></head><body>
      <details>
        <summary>What are collection solutions?</summary>
        <p>Collection solutions are the data, verification, and contact tools.</p>
      </details>
      <p>Collection solutions are the data, verification, and contact tools.
      Skip tracing covers nationwide addresses, scored phones, and right-party contact.</p>
    </body></html>
    """
    units = extract_html(html, url="https://sample-data.example.com/collections")
    answers = "\n".join(unit.answer_verbatim for unit in units)
    assert "right-party contact" in answers
