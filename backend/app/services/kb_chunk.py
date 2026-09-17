from __future__ import annotations

from dataclasses import dataclass, replace

from app.services.kb_embedder import count_embed_tokens, split_text_to_token_limit
from app.services.kb_extract.text import tidy_text
from app.services.kb_extract.types import EvidenceUnit


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
    context_prefix: str = ""
    enabled: bool = True
    review_note: str | None = None


def pack_chunks(unit: EvidenceUnit, target: int = 900, overlap: int = 150) -> list[TextChunk]:
    answer = tidy_text(unit.answer_verbatim)
    prefix = _embed_prefix(unit)
    source = tidy_text(unit.structured_text) if unit.structured_text is not None else answer
    room = max(32, target - len(prefix) - (1 if prefix else 0))
    pieces = _split_text(source, room, overlap)
    chunks: list[TextChunk] = []
    for piece in pieces:
        body = f"{prefix}\n{piece}" if prefix else piece
        chunks.append(
            TextChunk(
                heading=unit.heading,
                body=body,
                kind=unit.kind,
                canonical_question=unit.canonical_question,
                answer_verbatim=piece,
                display_locator=unit.display_locator,
                aliases=unit.aliases,
                topic=unit.topic,
                context_prefix=prefix if unit.structured_text is not None else "",
                enabled=unit.enabled,
                review_note=unit.review_note,
            )
        )
    return chunks


def _embed_prefix(unit: EvidenceUnit) -> str:
    parts = [unit.heading.strip()]
    if unit.canonical_question:
        parts.append(unit.canonical_question.strip())
    if unit.aliases:
        parts.append(" | ".join(alias for alias in unit.aliases if alias))
    return "\n".join(dict.fromkeys(part for part in parts if part))


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
        if count_embed_tokens(chunk.body) <= max_tokens:
            expanded.append(chunk)
            continue
        if chunk.context_prefix:
            prefix = chunk.context_prefix + "\n"
            room = max_tokens - count_embed_tokens(prefix) - 1
            clean = chunk.body[len(prefix) :]
            if room < 1:
                prefix, room = "", max_tokens
            expanded.extend(
                replace(chunk, body=f"{prefix}{piece}")
                for piece in split_text_to_token_limit(clean, room)
            )
            continue
        prefix = chunk.body[: -len(chunk.answer_verbatim)] if chunk.answer_verbatim else ""
        room = max_tokens - count_embed_tokens(prefix) - 1
        if room < 1:
            prefix = ""
            room = max_tokens
        for answer in split_text_to_token_limit(chunk.answer_verbatim, room):
            expanded.append(replace(chunk, body=f"{prefix}{answer}", answer_verbatim=answer))
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
    return _hard_split(text, target, overlap)


def _hard_split(text: str, target: int, overlap: int) -> list[str]:
    if len(text) <= target:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + target, len(text))
        if end < len(text):
            boundary = max(
                text.rfind("\n", start + target // 2, end),
                text.rfind(" ", start + target // 2, end),
            )
            if boundary > start:
                end = boundary + 1
        pieces.append(text[start:end])
        if end >= len(text):
            break
        next_start = max(end - min(overlap, target // 2), start + 1)
        if next_start > 0 and not text[next_start - 1].isspace():
            boundary = text.find(" ", next_start, end)
            if boundary >= 0:
                next_start = boundary + 1
        start = next_start
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
        prefix = prev[-take:] if take else ""
        if prefix and take < len(prev) and not prev[-take - 1].isspace():
            prefix = prefix.partition(" ")[2]
        overlapped.append(prefix + separator + piece if prefix else piece)
    return overlapped
