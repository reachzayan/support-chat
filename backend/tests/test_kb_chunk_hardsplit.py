from dataclasses import replace

from app.services.kb_chunk import pack_chunks
from app.services.kb_extract.types import EvidenceUnit


def _unit(answer: str, kind: str = "prose") -> EvidenceUnit:
    return EvidenceUnit(
        kind=kind,  # type: ignore[arg-type]
        heading="Turnaround",
        canonical_question=None
        if kind != "faq"
        else "How quickly are drug screening results available?",
        answer_verbatim=answer,
        body_for_search=f"Turnaround {answer}",
        display_locator="#faq",
    )


def test_six_thousand_as_hard_splits_with_overlap() -> None:
    unit = _unit("a" * 6000)
    chunks = pack_chunks(unit, target=1800, overlap=200)
    assert len(chunks) >= 3
    assert all(len(chunk.body) <= 1800 for chunk in chunks)
    assert chunks[0].body[-200:] == chunks[1].body[:200]
    assert all(chunk.answer_verbatim == chunk.body for chunk in chunks)


def test_short_faq_stays_one_chunk_with_question_copied() -> None:
    answer = "Most negative results are reported within 24-48 hours."
    unit = _unit(answer, kind="faq")
    chunks = pack_chunks(unit, target=1800, overlap=200)
    assert len(chunks) == 1
    assert chunks[0].body == answer
    assert chunks[0].canonical_question == "How quickly are drug screening results available?"
    assert chunks[0].answer_verbatim == answer
    assert "24-48" in chunks[0].answer_verbatim


def test_paragraph_split_preserves_numeric_span() -> None:
    unit = _unit("First paragraph.\n\nMost negative results are reported within 24-48 hours.")
    chunks = pack_chunks(unit, target=1800, overlap=200)
    assert len(chunks) == 1
    assert "24-48 hours" in chunks[0].answer_verbatim
    assert "24 - 48" not in chunks[0].answer_verbatim


def test_overlap_question_copied_onto_every_fragment() -> None:
    unit = replace(_unit("a" * 4000, kind="faq"))
    chunks = pack_chunks(unit, target=1800, overlap=200)
    assert len(chunks) >= 2
    assert all(
        chunk.canonical_question == "How quickly are drug screening results available?"
        for chunk in chunks
    )
    assert all(chunk.heading == "Turnaround" for chunk in chunks)
