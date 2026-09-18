"""Temporary, opt-in HTTP access to the same persisted visitor chat pipeline."""

import time
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db import SessionDep
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.visitor import Visitor
from app.repositories.message_repo import MessageRepository
from app.repositories.site_repo import SiteRepository
from app.security.deps import CurrentAdmin
from app.services.bot_trace import capture_trace, record_trace, wait_for_trace_tasks
from app.services.conversation_service import CommandError, CommandResult, ConversationService
from app.services.grounded_response import ProviderStatus, ResponseDecision, ResponseOutcome
from app.settings import get_settings


def require_eval_enabled() -> None:
    settings = get_settings()
    if not settings.internal_eval_enabled or settings.app_env != "local":
        raise HTTPException(404, "Not Found")


router = APIRouter(
    prefix="/api/internal/eval",
    tags=["Temporary evaluation"],
    dependencies=[Depends(require_eval_enabled)],
)


class EvalTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    site_key: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    client_message_id: UUID = Field(default_factory=uuid4)
    wait_for_handoff_summary: bool = True

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value


@router.post("/turn")
async def eval_turn(payload: EvalTurn, session: SessionDep, _admin: CurrentAdmin) -> JSONResponse:
    site = await SiteRepository(session).get_by_key(payload.site_key)
    if site is None or not site.enabled:
        raise HTTPException(404, "Not found")
    if not site.allowed_origins:
        raise HTTPException(409, "Site needs an allowed origin")
    if payload.conversation_id is None:
        visitor = Visitor(
            site_id=site.id,
            resume_token_hash="eval-" + uuid4().hex,
            name="Eval Visitor",
            email="eval@supportchat.local",
        )
        session.add(visitor)
        await session.flush()
        conversation = Conversation(site_id=site.id, visitor_id=visitor.id, state="bot")
        session.add(conversation)
        await session.commit()
    else:
        conversation = await session.get(Conversation, payload.conversation_id)
        if conversation is None or conversation.site_id != site.id:
            raise HTTPException(404, "Not found")
        visitor = await session.get(Visitor, conversation.visitor_id)
        if visitor is None or not visitor.resume_token_hash.startswith("eval-"):
            raise HTTPException(404, "Not found")
    messages = MessageRepository(session)
    latest = await messages.latest(conversation.id)
    cursor = latest.id if latest else 0
    conversation_id = conversation.id
    before = conversation.state
    started = time.perf_counter_ns()
    with capture_trace() as trace:
        service = ConversationService(session)
        try:
            result = await service.visitor_message(
                conversation.id,
                visitor.id,
                site.allowed_origins[0],
                payload.client_message_id,
                payload.message,
            )
            if result.generation_id is not None:
                await service.run_bot_turn(conversation.id, result.generation_id)
        except CommandError as exc:
            await session.rollback()
            if exc.code == "rate_limited":
                settings = get_settings()
                return JSONResponse(
                    {"detail": exc.code, "conversation_id": str(conversation_id)},
                    status_code=429,
                    headers={
                        "Cache-Control": "no-store",
                        "Retry-After": str(
                            max(
                                settings.rate_visitor_submit_window,
                                settings.rate_visitor_submit_ip_window,
                            )
                        ),
                    },
                )
            raise HTTPException(409, exc.code) from None
        if payload.wait_for_handoff_summary:
            wait_started = time.perf_counter_ns()
            pending = await wait_for_trace_tasks(
                timeout=min(2 * get_settings().haiku_timeout + 2, 30),
            )
            record_trace(
                "background_work",
                waited=True,
                pending=pending,
                timed_out=bool(pending),
                wait_ms=(time.perf_counter_ns() - wait_started) // 1_000_000,
            )
        else:
            record_trace("background_work", waited=False)
        rows = await messages.list_after(conversation.id, cursor)
        await session.refresh(conversation)
        _record_final_trace(trace, conversation, rows, before, result, site.bot_enabled)
        data = {
            "conversation_id": conversation.id,
            "client_message_id": payload.client_message_id,
            "duplicate": result.duplicate,
            "state_before": before,
            "state": conversation.state,
            "fallback_count": conversation.fallback_count,
            "intent": conversation.intent,
            "elapsed_ms": (time.perf_counter_ns() - started) // 1_000_000,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "body": m.body,
                    "system_reason": m.system_reason,
                    "outcome": m.response_outcome,
                    "reason": m.response_reason_code,
                    "source_chunk_ids": m.source_chunk_ids,
                    "citations": [
                        {
                            "chunk_id": c.chunk_id,
                            "source_url": c.source_url,
                            "source_title": c.source_title,
                            "cited_text": c.cited_text,
                            "response_start": c.response_start,
                            "response_end": c.response_end,
                            "source_start": c.source_start,
                            "source_end": c.source_end,
                        }
                        for c in m.citations
                    ],
                }
                for m in rows
            ],
            "trace": trace,
        }
    return JSONResponse(jsonable_encoder(data), headers={"Cache-Control": "no-store"})


def _record_final_trace(
    trace: dict[str, Any],
    conversation: Conversation,
    rows: list[Message],
    before: str,
    result: CommandResult,
    bot_enabled: bool,
) -> None:
    """Normalize provider-free exits against what was actually committed."""
    replies = [row for row in rows if row.role in {"bot", "system"}]
    if "decision" not in trace:
        classification = trace.get("classification", {})
        reason = (
            "duplicate"
            if result.duplicate
            else "policy_sensitive"
            if classification.get("sensitive_category", "none") != "none"
            else conversation.escalation_reason
            if conversation.state in {"queued", "callback"} and replies
            else "chitchat"
            if classification.get("chitchat")
            else "contact"
            if classification.get("contact")
            else "not_bot_state"
            if before != "bot"
            else "bot_disabled"
            if not bot_enabled
            else "transfer_consent_reply"
            if result.generation_id is None
            else "generation_discarded"
        )
        record_trace(
            "decision",
            decision=ResponseDecision(
                outcome=ResponseOutcome.BOUNDARY
                if reason in {"policy_sensitive", "visitor_request"}
                else None,
                reason_code=reason,
                body="\n\n".join(row.body for row in replies),
                offer_handoff=reason == "policy_sensitive",
            ),
        )
    if "provider" not in trace:
        record_trace("provider", status=ProviderStatus.NOT_USED)
    if "retrieval" not in trace:
        record_trace("retrieval", used=False)
    record_trace(
        "final",
        persisted=True,
        state_before=before,
        state=conversation.state,
        duplicate=result.duplicate,
        message_ids=[row.id for row in rows],
        reply_ids=[row.id for row in replies],
        reply_persisted=bool(replies),
        generation_id=result.generation_id,
    )
