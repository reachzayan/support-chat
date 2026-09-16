from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.services.kb_embedder import split_text_to_token_limit
from app.services.kb_extract.text import tidy_text
from app.services.kb_extract.types import EvidenceUnit

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class TextChunk:
    heading: str
    body: str
    kind: str = "prose"
    canonical_question: str | None = None
    answer_verbatim: str = ""
    display_locator: str | None = None
    aliases: tuple[str, ...] = ()
    topic: str | None = None


def pack_chunks(unit: EvidenceUnit, target: int = 1800, overlap: int = 200) -> list[TextChunk]:
    answer = tidy_text(unit.answer_verbatim)
    pieces = _split_text(answer, target, overlap)
    chunks: list[TextChunk] = []
    for piece in pieces:
        chunks.append(
            TextChunk(
                heading=unit.heading,
                body=piece,
                kind=unit.kind,
                canonical_question=unit.canonical_question,
                answer_verbatim=piece,
                display_locator=unit.display_locator,
                aliases=unit.aliases,
                topic=unit.topic,
            )
        )
    return chunks


def chunk_text(title: str, text: str) -> list[TextChunk]:
    unit = EvidenceUnit(
        kind="prose",
        heading=title,
        canonical_question=None,
        answer_verbatim=text,
        body_for_search=f"{title}\n{text}",
        display_locator=None,
    )
    return pack_chunks(unit)


def split_chunks_for_embed(chunks: list[TextChunk], max_tokens: int) -> list[TextChunk]:
    expanded: list[TextChunk] = []
    for chunk in chunks:
        for body in split_text_to_token_limit(chunk.body, max_tokens):
            expanded.append(replace(chunk, body=body, answer_verbatim=body))
    return expanded


def _split_text(text: str, target: int, overlap: int) -> list[str]:
    if len(text) <= target:
        return [text] if text else []
    paragraphs = [part for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        paragraphs = [text]
    packed: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > target:
            if current:
                packed.append(current)
                current = ""
            packed.extend(_split_sentences(paragraph, target, overlap))
            continue
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= target:
            current = candidate
            continue
        if current:
            packed.append(current)
        current = paragraph
    if current:
        packed.append(current)
    return _apply_overlap(packed, overlap, target) if packed else []


def _split_sentences(text: str, target: int, overlap: int) -> list[str]:
    sentences = [part for part in SENTENCE_SPLIT.split(text) if part]
    if not sentences:
        return _hard_split(text, target, overlap)
    packed: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > target:
            if current:
                packed.append(current)
                current = ""
            packed.extend(_hard_split(sentence, target, overlap))
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= target:
            current = candidate
            continue
        if current:
            packed.append(current)
        current = sentence
    if current:
        packed.append(current)
    return packed


def _hard_split(text: str, target: int, overlap: int) -> list[str]:
    if len(text) <= target:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + target, len(text))
        pieces.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return pieces


def _apply_overlap(pieces: list[str], overlap: int, target: int) -> list[str]:
    if overlap <= 0 or len(pieces) < 2:
        return pieces
    overlapped = [pieces[0]]
    for piece in pieces[1:]:
        prev = overlapped[-1]
        prefix_len = min(overlap, len(prev))
        prefix = prev[-prefix_len:] if prefix_len else ""
        if prefix and piece.startswith(prefix):
            overlapped.append(piece)
            continue
        room = target - len(piece)
        if room <= 0 or not prefix:
            overlapped.append(piece)
            continue
        separator = " " if not piece[:1].isspace() else ""
        take = min(prefix_len, max(0, room - len(separator)))
        overlapped.append(prev[-take:] + separator + piece)
    return overlapped
