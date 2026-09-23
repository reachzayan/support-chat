"""Local staff workbench over the real persisted visitor-chat pipeline."""

from __future__ import annotations

import time
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.visitor import Visitor
from app.repositories.message_repo import MessageRepository
from app.repositories.site_repo import SiteRepository
from app.services.bot_trace import capture_trace, record_trace, wait_for_trace_tasks
from app.services.conversation_service import CommandError, CommandResult, ConversationService
from app.services.grounded_response import ProviderStatus, ResponseDecision, ResponseOutcome
from app.settings import get_settings


@dataclass(frozen=True)
class InternalChatRequest:
    site_key: str
    message: str
    conversation_id: UUID | None
    client_message_id: UUID


class InternalChatError(Exception):
    def __init__(self, code: str, *, status_code: int) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class InternalChatHarness:
    """Drive one turn through ConversationService and return its committed result."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._sites = SiteRepository(session)
        self._messages = MessageRepository(session)

    async def turn(
        self,
        request: InternalChatRequest,
        *,
        diagnostics: bool,
    ) -> dict[str, Any]:
        site = await self._sites.get_by_key(request.site_key)
        if site is None or not site.enabled:
            raise InternalChatError("not_found", status_code=404)
        if not site.allowed_origins:
            raise InternalChatError("site_has_no_allowed_origin", status_code=409)

        conversation, visitor = await self._conversation(site.id, request.conversation_id)
        latest = await self._messages.latest(conversation.id)
        cursor = latest.id if latest is not None else 0
        state_before = conversation.state
        started = time.perf_counter_ns()
        trace_context = capture_trace() if diagnostics else nullcontext({})

        with trace_context as trace:
            record_trace(
                "request",
                site_key=request.site_key,
                conversation_id=conversation.id,
                client_message_id=request.client_message_id,
                message=request.message,
            )
            service = ConversationService(self._session)
            try:
                result = await service.visitor_message(
                    conversation.id,
                    visitor.id,
                    site.allowed_origins[0],
                    request.client_message_id,
                    request.message,
                )
                if result.generation_id is not None:
                    await service.run_bot_turn(conversation.id, result.generation_id)
            except CommandError as exc:
                await self._session.rollback()
                status_code = 429 if exc.code == "rate_limited" else 409
                raise InternalChatError(exc.code, status_code=status_code) from None

            if diagnostics:
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

            rows = await self._messages.list_after(conversation.id, cursor)
            await self._session.refresh(conversation)
            if diagnostics:
                self._record_final_trace(
                    trace,
                    conversation,
                    rows,
                    state_before,
                    result,
                    site.bot_enabled,
                )
            elapsed_ms = (time.perf_counter_ns() - started) // 1_000_000
            messages = [self._message_payload(row) for row in rows]
            reply = next(
                (row for row in reversed(messages) if row["role"] in {"bot", "system"}),
                None,
            )
            payload: dict[str, Any] = {
                "conversation_id": conversation.id,
                "client_message_id": request.client_message_id,
                "duplicate": result.duplicate,
                "state_before": state_before,
                "state": conversation.state,
                "fallback_count": conversation.fallback_count,
                "intent": conversation.intent,
                "elapsed_ms": elapsed_ms,
                "messages": messages,
                "reply": reply,
            }
            if diagnostics:
                payload["trace"] = trace
            return payload

    async def _conversation(
        self,
        site_id: UUID,
        conversation_id: UUID | None,
    ) -> tuple[Conversation, Visitor]:
        if conversation_id is None:
            visitor = Visitor(
                site_id=site_id,
                resume_token_hash="internal-dev-" + uuid4().hex,
                name="Internal Dev Visitor",
                email="internal-dev@supportchat.local",
            )
            self._session.add(visitor)
            await self._session.flush()
            conversation = Conversation(site_id=site_id, visitor_id=visitor.id, state="bot")
            self._session.add(conversation)
            await self._session.commit()
            return conversation, visitor

        conversation = await self._session.get(Conversation, conversation_id)
        if conversation is None or conversation.site_id != site_id:
            raise InternalChatError("not_found", status_code=404)
        visitor = await self._session.get(Visitor, conversation.visitor_id)
        if visitor is None or not visitor.resume_token_hash.startswith("internal-dev-"):
            raise InternalChatError("not_found", status_code=404)
        return conversation, visitor

    @staticmethod
    def _message_payload(message: Message) -> dict[str, Any]:
        return {
            "id": message.id,
            "role": message.role,
            "body": message.body,
            "client_message_id": message.client_message_id,
            "system_reason": message.system_reason,
            "outcome": message.response_outcome,
            "reason": message.response_reason_code,
            "source_article_ids": message.source_article_ids,
            "source_chunk_ids": message.source_chunk_ids,
            "snapshot_id": message.snapshot_id,
            "source_urls": message.source_urls,
            "source_title": message.source_title,
            "display_locator": message.display_locator,
            "created_at": message.created_at,
            "citations": [
                {
                    "id": citation.id,
                    "chunk_id": citation.chunk_id,
                    "snapshot_id": citation.snapshot_id,
                    "source_url": citation.source_url,
                    "source_title": citation.source_title,
                    "cited_text": citation.cited_text,
                    "response_start": citation.response_start,
                    "response_end": citation.response_end,
                    "source_start": citation.source_start,
                    "source_end": citation.source_end,
                }
                for citation in message.citations
            ],
        }

    @staticmethod
    def _record_final_trace(
        trace: dict[str, Any],
        conversation: Conversation,
        rows: list[Message],
        state_before: str,
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
                if state_before != "bot"
                else "bot_disabled"
                if not bot_enabled
                else "transfer_consent_reply"
                if result.generation_id is None
                else "generation_discarded"
            )
            record_trace(
                "decision",
                decision=ResponseDecision(
                    outcome=(
                        ResponseOutcome.BOUNDARY
                        if reason in {"policy_sensitive", "visitor_request"}
                        else None
                    ),
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
            state_before=state_before,
            state=conversation.state,
            duplicate=result.duplicate,
            message_ids=[row.id for row in rows],
            reply_ids=[row.id for row in replies],
            reply_persisted=bool(replies),
            generation_id=result.generation_id,
        )
