"""Haiku one-shot machine summary for handoff contexts."""

from __future__ import annotations

import time
from uuid import UUID

import structlog
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session_maker
from app.llm.prompts import HANDOFF_SUMMARY_PROMPT
from app.repositories.handoff_repo import HandoffRepository
from app.repositories.message_repo import MessageRepository
from app.services.bot_trace import record_trace, trace_active
from app.services.pii_redactor import redact_for_model
from app.settings import get_settings

log = structlog.get_logger("handoff_summary")

SUMMARY_FALLBACK = "(auto-summary unavailable in this environment)"
SUMMARY_MAX_CHARS = 800
TRANSCRIPT_LIMIT = 12


async def generate(
    session: AsyncSession,
    *,
    handoff_id: UUID,
    conversation_id: UUID,
    original_question: str,
    escalation_reason: str,
) -> str:
    settings = get_settings()
    model = (settings.haiku_model or settings.anthropic_model).strip()
    started = time.perf_counter()
    if not settings.anthropic_api_key:
        await HandoffRepository(session).update_summary(handoff_id, SUMMARY_FALLBACK, "")
        log.info(
            "handoff_summary",
            handoff_id=str(handoff_id),
            model="",
            elapsed_ms=0,
            output_len=len(SUMMARY_FALLBACK),
        )
        record_trace(
            "handoff_summary",
            status="fallback",
            reason="provider_not_configured",
            body=SUMMARY_FALLBACK,
            model="",
            elapsed_ms=0,
        )
        return SUMMARY_FALLBACK

    transcript = await _transcript_block(session, conversation_id)
    prompt = HANDOFF_SUMMARY_PROMPT.format(
        escalation_reason=escalation_reason,
        original_question=redact_for_model(original_question)[:500],
        transcript=transcript,
    )
    summary = await _call_haiku(prompt, model=model, timeout=settings.haiku_timeout, attempt=1)
    if not summary:
        summary = await _call_haiku(prompt, model=model, timeout=settings.haiku_timeout, attempt=2)
    if not summary:
        summary = SUMMARY_FALLBACK
        model_stored = ""
    else:
        model_stored = model
        if len(summary) > SUMMARY_MAX_CHARS:
            summary = summary[:SUMMARY_MAX_CHARS]
    await HandoffRepository(session).update_summary(handoff_id, summary, model_stored)
    record_trace(
        "handoff_summary",
        status="completed" if model_stored else "fallback",
        body=summary,
        model=model_stored,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
    )
    log.info(
        "handoff_summary",
        handoff_id=str(handoff_id),
        model=model_stored,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        output_len=len(summary),
    )
    return summary


async def generate_in_background(
    handoff_id: UUID,
    conversation_id: UUID,
    original_question: str,
    escalation_reason: str,
) -> None:
    try:
        async with session_maker()() as session:
            await generate(
                session,
                handoff_id=handoff_id,
                conversation_id=conversation_id,
                original_question=original_question,
                escalation_reason=escalation_reason,
            )
            await session.commit()
            record_trace("handoff_summary", persisted=True)
    except Exception as exc:
        record_trace(
            "handoff_summary",
            status="failed",
            persisted=False,
            error_class=type(exc).__name__,
        )
        log.info(
            "handoff_summary",
            handoff_id=str(handoff_id),
            model="",
            elapsed_ms=0,
            output_len=0,
            error_class=type(exc).__name__,
        )


async def _transcript_block(session: AsyncSession, conversation_id: UUID) -> str:
    rows = await MessageRepository(session).list_recent_roles(
        conversation_id, {"visitor", "bot", "system", "agent"}, TRANSCRIPT_LIMIT
    )
    lines: list[str] = []
    for message in rows:
        role = message.role
        body = redact_for_model(message.body or "").strip()
        if not body:
            continue
        lines.append(f"{role}: {body[:400]}")
    return "\n".join(lines) if lines else "(no prior turns)"


async def _call_haiku(prompt: str, *, model: str, timeout: float, attempt: int) -> str:
    settings = get_settings()
    client_kwargs: dict = {"timeout": timeout, "max_retries": 0}
    if settings.anthropic_api_key:
        client_kwargs["api_key"] = settings.anthropic_api_key
    client = AsyncAnthropic(**client_kwargs)
    section = f"handoff_summary_provider_{attempt}"
    started = time.perf_counter()
    record_trace(section, model=model, max_tokens=settings.haiku_max_tokens, prompt=prompt)
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=settings.haiku_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        record_trace(
            section,
            error_class=type(exc).__name__,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )
        log.info("provider_failure", error_class=type(exc).__name__, elapsed_ms=0)
        return ""
    finally:
        await client.close()
    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    body = " ".join(parts).strip()
    if trace_active():
        usage = getattr(response, "usage", None)
        record_trace(
            section,
            body=body,
            stop_reason=getattr(response, "stop_reason", None),
            request_id=getattr(response, "_request_id", None),
            usage=usage.model_dump() if hasattr(usage, "model_dump") else None,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )
    return body
