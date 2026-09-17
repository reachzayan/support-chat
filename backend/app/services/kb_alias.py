from __future__ import annotations

import asyncio
import json
import re

from app.llm.prompts import ALIAS_PROMPT
from app.services.kb_extract.types import EvidenceUnit
from app.settings import get_settings

HAIKU_MODEL = "claude-haiku-4-5-20251001"
INJECTION_MARKERS = (
    "system prompt",
    "ignore prior",
    "<script",
    "javascript:",
    "onerror",
)
URL_RE = re.compile(r"https?://", re.IGNORECASE)


async def generate_aliases(unit: EvidenceUnit) -> tuple[str, ...]:
    if unit.kind != "faq" or not unit.canonical_question:
        return unit.aliases
    settings = get_settings()
    if not settings.anthropic_api_key:
        return unit.aliases
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=10)
    prompt = ALIAS_PROMPT.format(
        heading=unit.heading,
        question=unit.canonical_question or unit.heading,
        answer=unit.answer_verbatim[:500],
    )
    try:
        response = await asyncio.wait_for(
            client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=10,
        )
    except Exception:
        return unit.aliases
    finally:
        await client.close()
    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text += getattr(block, "text", "")
    return tuple(dict.fromkeys((*unit.aliases, *_parse_aliases(text))))


def _load_alias_payload(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            return None
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None


def _valid_alias_item(item) -> str | None:
    if not isinstance(item, str):
        return None
    value = item.strip()
    if not value or len(value) >= 120:
        return None
    lowered = value.casefold()
    if URL_RE.search(value) or "<" in value or ">" in value:
        return None
    if any(marker in lowered for marker in INJECTION_MARKERS):
        return None
    return value


def _parse_aliases(raw: str) -> tuple[str, ...]:
    payload = _load_alias_payload(raw)
    if not isinstance(payload, list):
        return ()
    aliases: list[str] = []
    for item in payload:
        value = _valid_alias_item(item)
        if value is None:
            continue
        aliases.append(value)
        if len(aliases) >= 8:
            break
    if len(aliases) < 3:
        return tuple(aliases)
    return tuple(aliases)
