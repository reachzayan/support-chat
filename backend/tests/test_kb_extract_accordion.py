from app.services.kb_extract import extract_html


def test_aria_controls_button_pairs_with_region() -> None:
    html = """
    <html><body>
    <button aria-controls="ans1">How quickly are drug screening results available?</button>
    <div id="ans1" role="region">Most negative results are reported within 24-48 hours.</div>
    </body></html>
    """
    units = extract_html(html, url="https://sample-site.example.com/#faq")
    faqs = [unit for unit in units if unit.kind == "faq"]
    assert len(faqs) == 1
    assert faqs[0].canonical_question == "How quickly are drug screening results available?"
    assert faqs[0].answer_verbatim == "Most negative results are reported within 24-48 hours."


def test_details_summary_is_extracted_as_faq() -> None:
    html = """
    <html><body>
    <details>
      <summary>How quickly are drug screening results available?</summary>
      Most negative results are reported within 24-48 hours.
    </details>
    </body></html>
    """
    units = extract_html(html, url="https://sample-site.example.com/faq")
    faqs = [unit for unit in units if unit.kind == "faq"]
    assert len(faqs) == 1
    assert faqs[0].canonical_question == "How quickly are drug screening results available?"
    assert "24-48 hours" in faqs[0].answer_verbatim


def test_missing_aria_controls_target_does_not_sink_the_page() -> None:
    html = """
    <html><body>
    <button aria-controls="missing">Broken accordion</button>
    <main>
      <h1>Turnaround</h1>
      <p>Most negative results are reported within 24-48 hours.</p>
    </main>
    </body></html>
    """
    units = extract_html(html, url="https://sample-site.example.com/faq")
    answers = " ".join(unit.answer_verbatim for unit in units)
    assert "24-48 hours" in answers
    assert all(unit.canonical_question != "Broken accordion" for unit in units)
