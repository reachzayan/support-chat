from pathlib import Path

from app.services.kb_extract import extract_html

FIXTURE = Path(__file__).parent / "fixtures" / "kb" / "samplesite_timing.html"


def test_extract_keeps_turnaround_and_drops_nav() -> None:
    html = FIXTURE.read_text()
    units = extract_html(html, url="https://sample-site.example.com/faq")
    assert units
    answers = " ".join(unit.answer_verbatim for unit in units)
    assert "24-48 hours" in answers
    assert "Careers" not in answers


def test_extract_skips_tiny_pages() -> None:
    units = extract_html("<html><body><p>Hi</p></body></html>", url="https://sample-site.example.com/faq")
    assert units == []


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


def test_jsonld_faq_wins_over_near_duplicate_dom_answer() -> None:
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
        "Collection solutions are data, verification, and contact tools."
    ]


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
