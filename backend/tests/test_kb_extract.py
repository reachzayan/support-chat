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
