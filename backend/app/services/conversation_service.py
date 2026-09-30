import time
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.display_citations import visitor_citation_payloads
from app.chat.outcome_copy import (
    chitchat_reply,
    contact_line,
    is_transfer_offer_body,
    keep_helping_line,
    transfer_offer_line,
)
from app.chat.state_machine import IllegalTransition, apply_event
from app.llm.intent import (
    classify_intent,
    classify_sensitive,
    is_chitchat,
    is_contact_request,
    is_escalate_request,
    is_transfer_consent,
    is_transfer_decline,
)
from app.llm.safety_markers import SensitiveCategory
from app.models.conversation import Conversation
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.message import Message
from app.models.message_citation import MessageCitation
from app.models.site import Site
from app.models.user import User
from app.models.visitor import Visitor
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.kb_chunk_repo import live_chunks_query
from app.repositories.message_repo import MessageRepository
from app.repositories.origins import InvalidOrigin, canonicalize_origin, sanitize_visitor_url
from app.repositories.site_repo import SiteRepository
from app.repositories.user_repo import UserRepository
from app.repositories.visitor_block_repo import VisitorBlockRepository
from app.repositories.visitor_repo import VisitorRepository
from app.services.bot_trace import record_trace
from app.services.bot_turn_service import BotTurnService
from app.services.conversation_input import (
    cap_user_agent,
    hash_resume_token,
    issue_resume_token,
    masked_email,
    masked_name,
    masked_phone,
    normalize_prechat,
    peer_ip,
    prechat_payload_hash,
    require_message_body,
    welcome_line,
)
from app.services.conversation_types import (
    BootstrapResult as BootstrapResult,
)
from app.services.conversation_types import (
    CommandError as CommandError,
)
from app.services.conversation_types import (
    CommandResult as CommandResult,
)
from app.services.conversation_types import ReturningIdentity, VisitorConversationSummary
from app.services.grounded_response import (
    Citation,
    EvidenceUnit,
    ProviderStatus,
    ResponseDecision,
    ResponseOutcome,
    _safe_technical_failure,
)
from app.services.handoff_service import EscalationReason, HandoffService, HandoffTrigger
from app.services.pii_redactor import redact_for_log
from app.services.rate_limit import RateLimiter, RateLimitExceeded, RateLimitUnavailable
from app.services.refusal_library import fallback_refusal_body, lookup_refusal
from app.settings import get_settings

log = structlog.get_logger("chat")

MAX_TITLE = 300
MAX_URL = 2048
ASSISTANT_LINE = "You're now chatting with the assistant."
CLOSED_BY_PREFIX = "This chat was closed by "
IDLE_WARNING_LINE = "This chat will close in 1 minute. Send a message to keep active."
IDLE_CLOSED_LINE = "This chat has been closed automatically."
IDLE_TTL = timedelta(minutes=5)
IDLE_WARN = IDLE_TTL - timedelta(minutes=1)
OPEN_IDLE_STATES = frozenset({"prechat", "bot", "queued", "human"})
SENSITIVE_LINE = "Please do not share Social Security numbers or other personal identifiers."
RESUMED_LINE = "This chat has been resumed."
RESET_LINE = "This chat was reset by the visitor."
VISITOR_HISTORY_LIMIT = 25


def _transition(state: str | None, event: str) -> str:
    try:
        return apply_event(state, event)
    except IllegalTransition as exc:
        raise CommandError("illegal_state") from exc


def _is_open_visitor_conflict(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    return "uq_conversations_open_visitor" in str(orig if orig is not None else exc)


class ConversationService:
    def __init__(self, session: AsyncSession, responder=None, embedder=None) -> None:
        self._session = session
        self._sites = SiteRepository(session)
        self._visitors = VisitorRepository(session)
        self._conversations = ConversationRepository(session)
        self._messages = MessageRepository(session)
        self._users = UserRepository(session)
        self._blocks = VisitorBlockRepository(session)
        self._bot_turn = BotTurnService(
            session, responder, embedder, evidence_loader=self._retrieve_evidence
        )
        self._pending_handoff_summary = None
        self._bootstrap_wakeups: list[Conversation] = []

    async def _commit_and_schedule(self) -> None:
        await self._session.commit()
        if self._pending_handoff_summary is not None:
            self._schedule_handoff_summary(self._pending_handoff_summary)
            self._pending_handoff_summary = None

    async def bootstrap(
        self,
        site_key: str,
        public_key: str,
        origin_header: str | None,
        resume_token: str | None,
        client_host: str | None,
        user_agent: str | None,
        action: str = "identify",
        conversation_id: UUID | None = None,
        replace_current: bool = False,
    ) -> BootstrapResult:
        for _ in range(3):
            try:
                result = await self._bootstrap_once(
                    site_key,
                    public_key,
                    origin_header,
                    resume_token,
                    client_host,
                    user_agent,
                    action,
                    conversation_id,
                    replace_current,
                )
                await self._commit_and_schedule()
                return result
            except IntegrityError as exc:
                await self._session.rollback()
                if _is_open_visitor_conflict(exc):
                    try:
                        result = await self._bootstrap_once(
                            site_key,
                            public_key,
                            origin_header,
                            resume_token,
                            client_host,
                            user_agent,
                            action,
                            conversation_id,
                            replace_current,
                        )
                        await self._commit_and_schedule()
                        return result
                    except IntegrityError:
                        await self._session.rollback()
        raise CommandError("not_found")

    async def _bootstrap_once(
        self,
        site_key: str,
        public_key: str,
        origin_header: str | None,
        resume_token: str | None,
        client_host: str | None,
        user_agent: str | None,
        action: str,
        conversation_id: UUID | None,
        replace_current: bool,
    ) -> BootstrapResult:
        self._validate_bootstrap_action(action, resume_token, conversation_id, replace_current)
        site = await self._sites.get_by_key(site_key)
        if site is None or site.public_key != public_key or not site.enabled:
            raise CommandError("not_found")
        parent_origin = self._require_allowlisted_origin(origin_header, site.allowed_origins)
        if action == "forget":
            await self._forget_visitor(site.id, resume_token)
            return self._bootstrap_result(site, parent_origin, mode="forgotten")

        peer = peer_ip(client_host)
        await self._reject_if_blocked(site.id, ip=peer)

        visitor, issued_resume, recognized = await self._resolve_visitor(
            site.id,
            resume_token,
            peer,
            cap_user_agent(user_agent),
            create_if_missing=action == "identify",
        )
        await self._reject_if_blocked(
            site.id,
            ip=str(visitor.ip) if visitor.ip is not None else peer,
            email=visitor.email,
            phone=visitor.phone,
        )
        if not recognized:
            return self._pending_prechat_bootstrap(site, visitor, parent_origin, issued_resume)

        return await self._recognized_bootstrap(
            site,
            visitor,
            parent_origin,
            action,
            conversation_id,
            replace_current,
        )

    async def _recognized_bootstrap(
        self,
        site: Site,
        visitor: Visitor,
        parent_origin: str,
        action: str,
        conversation_id: UUID | None,
        replace_current: bool,
    ) -> BootstrapResult:
        if action == "history":
            return await self._history_bootstrap(site, visitor, parent_origin)
        if action == "refresh":
            assert conversation_id is not None
            conversation = await self._refresh_conversation(site, visitor, conversation_id)
            return await self._conversation_bootstrap(
                site, visitor, conversation, parent_origin, None
            )
        if action == "open":
            assert conversation_id is not None
            conversation = await self._resume_conversation(
                site, visitor, conversation_id, replace_current=replace_current
            )
            return await self._conversation_bootstrap(
                site, visitor, conversation, parent_origin, None
            )
        if action == "reset":
            await self._reset_current_conversation(site.id, visitor.id)
            return self._pending_prechat_bootstrap(site, visitor, parent_origin, None)
        if action != "identify":
            raise CommandError("invalid")

        current = await self._conversations.get_open_for_visitor(site.id, visitor.id)
        chat_count = await self._conversations.count_for_visitor_history(site.id, visitor.id)
        if chat_count > 0 and visitor.name and visitor.email:
            return self._bootstrap_result(
                site,
                parent_origin,
                mode="identity",
                visitor_id=visitor.id,
                identity=self._returning_identity(visitor, chat_count),
            )
        if current is not None and not (
            current.state == "prechat" and current.prechat_submission_id is None
        ):
            return await self._conversation_bootstrap(site, visitor, current, parent_origin, None)
        return self._pending_prechat_bootstrap(site, visitor, parent_origin, None)

    async def _reject_if_blocked(
        self,
        site_id: UUID,
        *,
        ip: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> None:
        clean_ip = peer_ip(ip)
        clean_email = email.strip().lower() if email and email.strip() else None
        clean_phone = phone.strip() if phone and phone.strip() else None
        if await self._blocks.is_blocked(
            site_id, ip=clean_ip, email=clean_email, phone=clean_phone
        ):
            raise CommandError("forbidden")

    @staticmethod
    def _validate_bootstrap_action(
        action: str,
        resume_token: str | None,
        conversation_id: UUID | None,
        replace_current: bool,
    ) -> None:
        if action != "identify" and not resume_token:
            raise CommandError("invalid")
        if action in {"open", "refresh"} and conversation_id is None:
            raise CommandError("invalid")
        if action not in {"open", "refresh"} and (conversation_id is not None or replace_current):
            raise CommandError("invalid")
        if action == "refresh" and replace_current:
            raise CommandError("invalid")

    async def _conversation_bootstrap(
        self,
        site: Site,
        visitor: Visitor,
        conversation: Conversation,
        parent_origin: str,
        resume_token: str | None,
    ) -> BootstrapResult:
        messages, has_older = await self._messages.list_before(conversation.id, None)
        assigned = await self.assigned_agent_view(conversation)
        return self._bootstrap_result(
            site,
            parent_origin,
            mode="conversation",
            resume_token=resume_token,
            visitor_id=visitor.id,
            conversation_id=conversation.id,
            conversation_state=conversation.state,
            assigned_agent=assigned,
            messages=messages,
            messages_has_older=has_older,
        )

    def _pending_prechat_bootstrap(
        self,
        site: Site,
        visitor: Visitor,
        parent_origin: str,
        resume_token: str | None,
    ) -> BootstrapResult:
        return self._bootstrap_result(
            site,
            parent_origin,
            mode="conversation",
            resume_token=resume_token,
            visitor_id=visitor.id,
            conversation_state="prechat",
            assigned_agent=None,
            messages=[],
            messages_has_older=False,
        )

    async def _history_bootstrap(
        self, site: Site, visitor: Visitor, parent_origin: str
    ) -> BootstrapResult:
        rows = await self._conversations.list_for_visitor_history(
            site.id, visitor.id, limit=VISITOR_HISTORY_LIMIT
        )
        total = await self._conversations.count_for_visitor_history(site.id, visitor.id)
        summaries = [
            VisitorConversationSummary(
                id=conversation.id,
                state=conversation.state,
                inquiry_type=conversation.inquiry_type,
                created_at=conversation.created_at,
                last_message_at=conversation.last_message_at,
                assigned_agent=(
                    {"id": str(agent.id), "display_name": agent.display_name}
                    if agent is not None
                    else None
                ),
                is_current=conversation.state != "closed",
            )
            for conversation, agent in rows
        ]
        return self._bootstrap_result(
            site,
            parent_origin,
            mode="history",
            visitor_id=visitor.id,
            identity=self._returning_identity(visitor, total),
            conversations=summaries,
        )

    def _bootstrap_result(
        self,
        site: Site,
        parent_origin: str,
        *,
        mode: Literal["conversation", "identity", "history", "forgotten"],
        **values,
    ) -> BootstrapResult:
        return BootstrapResult(
            site_key=site.key,
            site_name=site.name,
            greeting=site.greeting,
            privacy_url=site.privacy_url,
            contact_info=list(site.contact_info or []),
            site_id=site.id,
            parent_origin=parent_origin,
            mode=mode,
            resume_token=values.pop("resume_token", None),
            bot_enabled=site.bot_enabled,
            human_enabled=site.human_enabled,
            changed_conversations=list(self._bootstrap_wakeups),
            **values,
        )

    @staticmethod
    def _returning_identity(visitor: Visitor, chat_count: int) -> ReturningIdentity:
        return ReturningIdentity(
            display_name=masked_name(visitor.name),
            email_hint=masked_email(visitor.email),
            phone_hint=masked_phone(visitor.phone),
            chat_count=chat_count,
        )

    @staticmethod
    def sanitize_hello_page(
        parent_origin: str, page_url: str, page_title: str, referrer: str
    ) -> tuple[str, str | None, str | None]:
        try:
            clean_url = sanitize_visitor_url(page_url, parent_origin, MAX_URL)
            clean_ref = ""
            if referrer:
                clean_ref = sanitize_visitor_url(referrer, parent_origin, MAX_URL)
        except InvalidOrigin as exc:
            raise CommandError("invalid") from exc
        title = (page_title or "").strip()[:MAX_TITLE]
        return clean_url, title or None, clean_ref or None

    async def hello(
        self,
        conversation_id: UUID,
        visitor_id: UUID,
        parent_origin: str,
        page_url: str,
        page_title: str,
        referrer: str,
    ) -> CommandResult:
        clean_url, title, clean_ref = self.sanitize_hello_page(
            parent_origin, page_url, page_title, referrer
        )
        conversation, site_key = await self._lock_visitor_conversation(
            conversation_id, visitor_id, parent_origin
        )
        conversation.page_url = clean_url
        conversation.page_title = title
        conversation.referrer = clean_ref
        await self._session.commit()
        log.info(
            "hello",
            conversation_id=str(conversation.id),
            site_key=site_key,
            role="visitor",
            length=len(clean_url),
        )
        return CommandResult(conversation=conversation, site_key=site_key, event="hello")

    async def submit_prechat(
        self,
        conversation_id: UUID | None,
        visitor_id: UUID,
        parent_origin: str,
        submission_id: UUID,
        name: str,
        email: str,
        phone: str,
        inquiry_type: str,
        message: str,
        client_ip: str | None = None,
        pending_hello: tuple[str, str | None, str | None] | None = None,
    ) -> CommandResult:
        clean = normalize_prechat(name, email, phone, inquiry_type, message)
        conversation, site_key = await self._lock_or_open_visitor_conversation(
            conversation_id, visitor_id, parent_origin, pending_hello
        )
        await self._reject_if_blocked(
            conversation.site_id,
            ip=client_ip,
            email=clean["email"],
            phone=clean["phone"] or None,
        )
        payload_hash = prechat_payload_hash(
            clean["name"], clean["email"], clean["phone"], clean["inquiry_type"], clean["message"]
        )
        if conversation.prechat_submission_id == submission_id:
            if conversation.prechat_payload_hash != payload_hash:
                raise CommandError("idempotency_conflict")
            existing = None
            if clean["message"]:
                existing = await self._messages.get_by_client_id(conversation.id, submission_id)
            await self._session.commit()
            return CommandResult(
                conversation=conversation,
                site_key=site_key,
                message=existing,
                event="prechat",
                submission_id=str(submission_id),
                duplicate=True,
            )
        await self._rate_limit_submit(conversation.site_id, visitor_id, client_ip)
        site = await self._sites.get_by_id(conversation.site_id)
        if site is None:
            raise CommandError("invalid")
        if site.bot_enabled:
            conversation.state = _transition(conversation.state, "submit_prechat")
        conversation.prechat_submission_id = submission_id
        conversation.prechat_payload_hash = payload_hash
        conversation.inquiry_type = clean["inquiry_type"]
        visitor = await self._visitors.lock_by_id(visitor_id)
        assert visitor is not None
        visitor.name = clean["name"]
        visitor.email = clean["email"]
        visitor.phone = clean["phone"] or None
        inserted = None
        generation_id = None
        if site.bot_enabled:
            await self._insert_message(
                conversation, "system", welcome_line(site.name, conversation.page_title)
            )
        if clean["message"]:
            inserted = await self._insert_message(
                conversation, "visitor", clean["message"], client_message_id=submission_id
            )
        else:
            conversation.last_message_at = datetime.now(UTC)
        if not site.bot_enabled:
            await self._enter_callback(conversation)
        elif clean["message"]:
            generation_id = await self._arm_bot_turn(conversation, site, clean["message"])
        await self._commit_and_schedule()
        log.info(
            "prechat",
            conversation_id=str(conversation.id),
            site_key=site_key,
            role="visitor",
            length=len(clean["message"]),
        )
        return CommandResult(
            conversation=conversation,
            site_key=site_key,
            message=inserted,
            event="prechat",
            submission_id=str(submission_id),
            generation_id=generation_id,
        )

    async def visitor_message(
        self,
        conversation_id: UUID,
        visitor_id: UUID,
        parent_origin: str,
        client_message_id: UUID,
        body: str,
        client_ip: str | None = None,
    ) -> CommandResult:
        text = require_message_body(body)
        conversation, site_key = await self._lock_visitor_conversation(
            conversation_id, visitor_id, parent_origin
        )
        existing = await self._messages.get_by_client_id(conversation.id, client_message_id)
        if existing is not None:
            if existing.role != "visitor" or existing.body != text:
                raise CommandError("idempotency_conflict")
            await self._session.commit()
            return CommandResult(
                conversation=conversation,
                site_key=site_key,
                message=existing,
                client_message_id=str(client_message_id),
                duplicate=True,
            )
        if conversation.state == "bot" and conversation.active_generation_id is not None:
            raise CommandError("assistant_busy")
        await self._rate_limit_submit(conversation.site_id, visitor_id, client_ip)
        conversation.state = _transition(conversation.state, "visitor_message")
        inserted = await self._insert_message(
            conversation, "visitor", text, client_message_id=client_message_id
        )
        site = await self._sites.get_by_id(conversation.site_id)
        if site is None:
            raise CommandError("invalid")
        generation_id = await self._arm_bot_turn(conversation, site, text)
        await self._commit_and_schedule()
        log.info(
            "visitor_message",
            conversation_id=str(conversation.id),
            site_key=site_key,
            role="visitor",
            length=len(text),
        )
        return CommandResult(
            conversation=conversation,
            site_key=site_key,
            message=inserted,
            client_message_id=str(client_message_id),
            generation_id=generation_id,
        )

    async def escalate(
        self, conversation_id: UUID, visitor_id: UUID, parent_origin: str
    ) -> CommandResult:
        conversation, site_key = await self._lock_visitor_conversation(
            conversation_id, visitor_id, parent_origin
        )
        site = await self._sites.get_by_id(conversation.site_id)
        if site is None:
            raise CommandError("invalid")
        conversation.intent = "escalate"
        inserted = None
        if await self._awaiting_transfer_consent(conversation.id):
            question = await self._latest_offered_question(conversation.id)
            await self._open_handoff(
                conversation,
                reason="visitor_request",
                original_question=question or "Visitor requested a specialist",
            )
        else:
            conversation.active_generation_id = None
            inserted = await self._insert_message(
                conversation, "system", keep_helping_line(site.name)
            )
        await self._commit_and_schedule()
        log.info(
            "escalate",
            conversation_id=str(conversation.id),
            site_key=site_key,
            role="visitor",
            length=0,
        )
        return CommandResult(
            conversation=conversation, site_key=site_key, event="escalate", message=inserted
        )

    async def join(self, conversation_id: UUID, agent: User) -> CommandResult:
        conversation, site_key = await self._lock_staff_conversation(conversation_id)
        site = await self._sites.get_by_id(conversation.site_id)
        if site is None or not site.human_enabled:
            raise CommandError("join_disabled")
        if conversation.state == "human":
            agent_id = conversation.assigned_agent_id
            name = ""
            if agent_id is not None:
                winner = await self._users.get_by_id(agent_id)
                if winner is not None:
                    name = winner.display_name
            raise CommandError("already_joined", display_name=name)
        conversation.state = _transition(conversation.state, "join")
        conversation.assigned_agent_id = agent.id
        conversation.active_generation_id = None
        line = f"You're now chatting with {agent.display_name}."
        inserted = await self._insert_message(conversation, "system", line)
        await self._session.commit()
        log.info(
            "join",
            conversation_id=str(conversation.id),
            site_key=site_key,
            role="system",
            length=len(line),
        )
        return CommandResult(
            conversation=conversation, site_key=site_key, message=inserted, event="join"
        )

    async def agent_message(
        self, conversation_id: UUID, agent: User, client_message_id: UUID, body: str
    ) -> CommandResult:
        text = require_message_body(body)
        conversation, site_key = await self._lock_staff_conversation(conversation_id)
        if conversation.assigned_agent_id != agent.id:
            raise CommandError("not_assigned")
        existing = await self._messages.get_by_client_id(conversation.id, client_message_id)
        if existing is not None:
            if (
                existing.role != "agent"
                or existing.body != text
                or existing.author_user_id != agent.id
            ):
                raise CommandError("idempotency_conflict")
            await self._session.commit()
            return CommandResult(
                conversation=conversation,
                site_key=site_key,
                message=existing,
                client_message_id=str(client_message_id),
                duplicate=True,
            )
        conversation.state = _transition(conversation.state, "agent_message")
        inserted = await self._insert_message(
            conversation,
            "agent",
            text,
            client_message_id=client_message_id,
            author_user_id=agent.id,
        )
        await self._session.commit()
        log.info(
            "agent_message",
            conversation_id=str(conversation.id),
            site_key=site_key,
            role="agent",
            length=len(text),
        )
        return CommandResult(
            conversation=conversation,
            site_key=site_key,
            message=inserted,
            client_message_id=str(client_message_id),
        )

    async def end(self, conversation_id: UUID, agent: User) -> CommandResult:
        conversation, site_key = await self._lock_staff_conversation(conversation_id)
        if conversation.assigned_agent_id != agent.id:
            raise CommandError("not_assigned")
        conversation.state = _transition(conversation.state, "end")
        conversation.closed_at = datetime.now(UTC)
        conversation.active_generation_id = None
        line = f"{CLOSED_BY_PREFIX}{agent.display_name}."
        inserted = await self._insert_message(conversation, "system", line)
        await self._session.commit()
        log.info(
            "end",
            conversation_id=str(conversation.id),
            site_key=site_key,
            role="system",
            length=len(line),
        )
        return CommandResult(
            conversation=conversation,
            site_key=site_key,
            message=inserted,
            event="end",
        )

    async def tick_idle(
        self, conversation_id: UUID, now: datetime | None = None
    ) -> CommandResult | None:
        moment = now or datetime.now(UTC)
        conversation, site = await self._lock_site_then_conversation(conversation_id)
        if conversation is None:
            return None
        site_key = site.key if site is not None else ""
        result = await self._apply_idle_tick(conversation, site_key, moment)
        await self._session.commit()
        return result

    async def close_expired(
        self, now: datetime | None = None, limit: int = 100
    ) -> list[CommandResult]:
        moment = now or datetime.now(UTC)
        cutoff = moment - IDLE_WARN
        rows = await self._conversations.list_expired_open(cutoff, limit=limit)
        results: list[CommandResult] = []
        for conversation in rows:
            site = await self._sites.get_by_id(conversation.site_id)
            site_key = site.key if site is not None else ""
            result = await self._apply_idle_tick(conversation, site_key, moment)
            if result is not None:
                results.append(result)
        await self._session.commit()
        return results

    async def _apply_idle_tick(
        self, conversation: Conversation, site_key: str, moment: datetime
    ) -> CommandResult | None:
        if not await self._idle_candidate(conversation):
            return None
        age = self._idle_age(conversation, moment)
        if age is None:
            return None
        if age >= IDLE_TTL:
            return await self._close_idle(conversation, site_key, moment)
        if age >= IDLE_WARN:
            inserted = await self._ensure_system_line(
                conversation, IDLE_WARNING_LINE, created_at=moment, touch_last_message=False
            )
            if inserted is None:
                return None
            return CommandResult(
                conversation=conversation,
                site_key=site_key,
                message=inserted,
                event="idle_warning",
            )
        return None

    async def _close_idle(
        self, conversation: Conversation, site_key: str, moment: datetime
    ) -> CommandResult:
        self._apply_idle_close(conversation, moment)
        await self._ensure_system_line(
            conversation,
            IDLE_WARNING_LINE,
            created_at=moment - (IDLE_TTL - IDLE_WARN),
            touch_last_message=False,
        )
        inserted = await self._ensure_system_line(
            conversation,
            IDLE_CLOSED_LINE,
            created_at=moment,
            touch_last_message=True,
            last_message_at=moment,
        )
        return CommandResult(
            conversation=conversation,
            site_key=site_key,
            message=inserted,
            event="end",
        )

    async def _ensure_system_line(
        self,
        conversation: Conversation,
        body: str,
        *,
        created_at: datetime,
        touch_last_message: bool,
        last_message_at: datetime | None = None,
    ) -> Message | None:
        if await self._messages.has_system_body(conversation.id, body):
            return None
        return await self._insert_message(
            conversation,
            "system",
            body,
            created_at=created_at,
            touch_last_message=touch_last_message,
            at=last_message_at,
        )

    async def _idle_candidate(self, conversation: Conversation | None) -> bool:
        if conversation is None or conversation.state not in OPEN_IDLE_STATES:
            return False
        if conversation.active_generation_id is not None:
            return False
        if conversation.state == "prechat" and not await self._messages.has_visitor_message(
            conversation.id
        ):
            return False
        return conversation.last_message_at is not None

    def _idle_age(self, conversation: Conversation, moment: datetime) -> timedelta | None:
        last_at = conversation.last_message_at
        if last_at is None:
            return None
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=UTC)
        return moment - last_at

    async def _idle_due(self, conversation: Conversation | None, moment: datetime) -> bool:
        if not await self._idle_candidate(conversation):
            return False
        assert conversation is not None
        age = self._idle_age(conversation, moment)
        return age is not None and age >= IDLE_TTL

    def _apply_idle_close(self, conversation: Conversation, moment: datetime) -> None:
        conversation.state = _transition(conversation.state, "end")
        conversation.closed_at = moment
        conversation.active_generation_id = None

    async def transfer_to_bot(self, conversation_id: UUID, agent: User) -> CommandResult:
        conversation, site_key = await self._lock_staff_conversation(conversation_id)
        if conversation.assigned_agent_id != agent.id:
            raise CommandError("not_assigned")
        site = await self._sites.get_by_id(conversation.site_id)
        if site is None or not site.bot_enabled:
            raise CommandError("bot_disabled")
        conversation.state = _transition(conversation.state, "transfer_to_bot")
        conversation.assigned_agent_id = None
        conversation.active_generation_id = None
        conversation.fallback_count = 0
        conversation.attention_needed = False
        conversation.escalation_reason = None
        inserted = await self._insert_message(conversation, "system", ASSISTANT_LINE)
        await self._session.commit()
        log.info(
            "transfer_to_bot",
            conversation_id=str(conversation.id),
            site_key=site_key,
            role="system",
            length=len(ASSISTANT_LINE),
        )
        return CommandResult(
            conversation=conversation,
            site_key=site_key,
            message=inserted,
            event="transfer_to_bot",
        )

    async def close_attention(self, conversation_id: UUID, agent: User) -> CommandResult:
        conversation, site_key = await self._lock_staff_conversation(conversation_id)
        if (
            conversation.state != "queued"
            or not conversation.attention_needed
            or conversation.assigned_agent_id is not None
        ):
            raise CommandError("illegal_state")
        conversation.state = _transition(conversation.state, "close_attention")
        conversation.closed_at = datetime.now(UTC)
        conversation.active_generation_id = None
        await self._session.commit()
        return CommandResult(conversation=conversation, site_key=site_key, event="end")

    async def _enter_callback(
        self,
        conversation: Conversation,
        stage_timings: dict[str, int] | None = None,
    ):
        question = await self._latest_visitor_body(conversation.id)
        return await self._open_handoff(
            conversation,
            reason="visitor_request",
            original_question=question or "Visitor submitted a callback request",
            stage_timings=stage_timings,
        )

    async def _open_handoff(
        self,
        conversation: Conversation,
        *,
        reason: EscalationReason,
        original_question: str,
        clarification_answer: str | None = None,
        candidate_unit_ids: list[UUID] | None = None,
        rejection_reasons: list[dict] | None = None,
        stage_timings: dict[str, int] | None = None,
        provider_status: str = "ok",
        snapshot_id: UUID | None = None,
    ):
        service = HandoffService(self._session)
        row = await service.open_handoff(
            HandoffTrigger(
                conversation_id=conversation.id,
                reason=reason,
                original_question=original_question,
                clarification_answer=clarification_answer,
                candidate_unit_ids=list(candidate_unit_ids or []),
                rejection_reasons=list(rejection_reasons or []),
                stage_timings=dict(stage_timings or {}),
                provider_status=provider_status,  # type: ignore[arg-type]
                snapshot_id=snapshot_id,
            )
        )
        await self._session.refresh(conversation)
        self._pending_handoff_summary = row
        return row

    def _schedule_handoff_summary(self, row) -> None:
        HandoffService(self._session).trace_summary_queued(row)

    async def _arm_bot_turn(self, conversation: Conversation, site: Site, text: str) -> UUID | None:
        if not site.bot_enabled:
            if conversation.state == "bot":
                await self._enter_callback(conversation)
            return None
        if conversation.state != "bot":
            return None
        conversation.intent = classify_intent(text)
        category = classify_sensitive(text)
        record_trace(
            "classification",
            intent=conversation.intent,
            sensitive_category=category.value,
            chitchat=is_chitchat(text),
            contact=is_contact_request(text),
            explicit_human_request=is_escalate_request(text),
        )
        if category is not SensitiveCategory.NONE:
            log.info(
                "sensitive_intent",
                conversation_id=str(conversation.id),
                category=category.value,
                preview=redact_for_log(text),
            )
            await self._commit_sensitive_refusal(conversation, site, category)
            return None
        if await self._handle_transfer_consent_reply(conversation, text):
            return None
        if is_escalate_request(text):
            conversation.active_generation_id = None
            await self._open_handoff(
                conversation,
                reason="visitor_request",
                original_question=text,
            )
            return None
        if is_contact_request(text) and site.contact_info:
            conversation.active_generation_id = None
            await self._insert_message(
                conversation, "system", contact_line(list(site.contact_info))
            )
            return None
        if is_chitchat(text):
            conversation.active_generation_id = None
            reply = chitchat_reply(text, site.contact_info, site_name=site.name)
            if reply:
                await self._insert_message(conversation, "system", reply)
            return None
        generation_id = uuid4()
        conversation.active_generation_id = generation_id
        conversation.generation_created_at = datetime.now(UTC)
        conversation.generation_lease_expires_at = None
        return generation_id

    async def _handle_transfer_consent_reply(self, conversation: Conversation, text: str) -> bool:
        if not await self._awaiting_transfer_consent(conversation.id):
            return False
        if is_transfer_consent(text) or is_escalate_request(text):
            conversation.active_generation_id = None
            await self._open_handoff(
                conversation,
                reason="visitor_request",
                original_question=await self._latest_offered_question(conversation.id),
            )
            return True
        if is_transfer_decline(text) or is_chitchat(text):
            conversation.active_generation_id = None
            conversation.fallback_count = 0
            return True
        return False

    async def _awaiting_transfer_consent(self, conversation_id: UUID) -> bool:
        recent = await self._messages.list_recent_roles(
            conversation_id, {"visitor", "bot", "system", "agent"}, 2
        )
        if len(recent) < 2:
            return False
        prior = recent[-2]
        if prior.role == "system" and is_transfer_offer_body(prior.body):
            return True
        if prior.role != "bot":
            return False
        from app.chat.outcome_copy import INSUFFICIENT_HUMAN, TECH_FAIL_HUMAN

        if prior.body in {INSUFFICIENT_HUMAN, TECH_FAIL_HUMAN} or is_transfer_offer_body(
            prior.body
        ):
            return True
        lowered = (prior.body or "").casefold()
        return "specialist" in lowered and (
            "would you like" in lowered
            or "connect you" in lowered
            or "confirm it" in lowered
            or "take it from here" in lowered
            or "can take over" in lowered
            or "pick up here" in lowered
        )

    async def _latest_offered_question(self, conversation_id: UUID) -> str:
        recent = await self._messages.list_recent_roles(conversation_id, {"visitor"}, 2)
        if len(recent) >= 2:
            return recent[-2].body
        return await self._latest_visitor_body(conversation_id)

    async def _commit_sensitive_refusal(
        self, conversation: Conversation, site: Site, category: SensitiveCategory
    ) -> None:
        refusal = await lookup_refusal(self._session, site.id, category)
        body = (
            refusal.body
            if refusal is not None
            else (fallback_refusal_body(category) or SENSITIVE_LINE)
        )
        conversation.active_generation_id = None
        if refusal is not None and refusal.chunk_id is not None:
            await self._insert_message(
                conversation,
                "bot",
                body,
                source_chunk_ids=[refusal.chunk_id],
                snapshot_id=refusal.snapshot_id,
                system_reason="sensitive",
                source_title="company policy",
                response_outcome=ResponseOutcome.BOUNDARY.value,
                response_reason_code="policy_sensitive",
            )
        else:
            await self._insert_message(
                conversation,
                "system",
                body,
                system_reason="sensitive",
                response_outcome=ResponseOutcome.BOUNDARY.value,
                response_reason_code="policy_sensitive",
            )
        await self._insert_message(
            conversation,
            "system",
            transfer_offer_line(human_enabled=site.human_enabled),
            system_reason="insufficient",
            response_outcome=ResponseOutcome.BOUNDARY.value,
            response_reason_code="policy_sensitive",
        )

    async def run_bot_turn(
        self, conversation_id: UUID, generation_id: UUID, *, already_claimed: bool = False
    ) -> CommandResult | None:
        if not already_claimed:
            claimed = await self._conversations.claim_generation(
                conversation_id,
                generation_id,
                lease=timedelta(seconds=get_settings().bot_generation_lease_seconds),
            )
            if not claimed:
                return None
        try:
            return await self._run_bot_turn(conversation_id, generation_id)
        except Exception:
            log.exception(
                "bot_turn_failed", conversation_id=str(conversation_id), role="bot", length=0
            )
            try:
                conversation = await self._conversations.get_by_id(conversation_id)
                if conversation is not None:
                    return await self._finalize_grounded_decision(
                        conversation_id,
                        generation_id,
                        conversation.site_id,
                        _safe_technical_failure(reason="provider_exception"),
                    )
            except Exception:
                log.exception("bot_turn_fail_persist_failed", conversation_id=str(conversation_id))
            await self._release_generation(conversation_id, generation_id)
            return None

    async def _run_bot_turn(
        self, conversation_id: UUID, generation_id: UUID
    ) -> CommandResult | None:
        conversation = await self._conversations.get_by_id(conversation_id)
        if conversation is None or conversation.state != "bot":
            return None
        if conversation.active_generation_id != generation_id:
            return None
        site = await self._sites.get_by_id(conversation.site_id)
        if site is None:
            return None
        if not site.bot_enabled:
            conversation, site, site_key = await self._lock_finalize_context(
                conversation_id, site.id
            )
            if conversation is None:
                return None
            if (
                site is not None
                and conversation.state == "bot"
                and conversation.active_generation_id == generation_id
            ):
                if site.bot_enabled:
                    conversation.fallback_count += 1
                    conversation.active_generation_id = None
                    message = await self._insert_message(
                        conversation,
                        "system",
                        transfer_offer_line(human_enabled=site.human_enabled),
                        system_reason="insufficient",
                    )
                    await self._session.commit()
                    return CommandResult(
                        conversation=conversation, site_key=site_key, message=message
                    )
                await self._enter_callback(conversation)
                await self._commit_and_schedule()
            else:
                await self._session.commit()
            return CommandResult(conversation=conversation, site_key=site_key)

        visitor_text = await self._latest_visitor_body(conversation_id)
        prepared = await self._bot_turn.prepare(conversation, site, visitor_text)
        return await self._finalize_grounded_decision(
            conversation_id,
            generation_id,
            site.id,
            prepared.decision,
            stage_timings=prepared.stage_timings,
        )

    async def _retrieve_evidence(
        self, site_id: UUID, visitor_text: str, stage_timings: dict[str, int] | None = None
    ) -> list[EvidenceUnit]:
        return await self._bot_turn.retrieve_evidence(site_id, visitor_text, stage_timings)

    async def _finalize_grounded_decision(
        self,
        conversation_id: UUID,
        generation_id: UUID,
        site_id: UUID,
        decision: ResponseDecision,
        *,
        stage_timings: dict[str, int] | None = None,
    ) -> CommandResult | None:
        timings = stage_timings if stage_timings is not None else {}
        record_trace("decision", decision=decision, stage_timings=timings)
        conversation, site, site_key = await self._lock_finalize_context(conversation_id, site_id)
        if conversation is None:
            return None
        if (
            site is None
            or conversation.state != "bot"
            or conversation.active_generation_id != generation_id
        ):
            await self._session.commit()
            return CommandResult(conversation=conversation, site_key=site_key)
        if not site.enabled or not site.bot_enabled:
            await self._enter_callback(conversation)
            await self._commit_and_schedule()
            return CommandResult(conversation=conversation, site_key=site_key)
        if decision.citations:
            started = time.perf_counter_ns()
            live = await self._grounded_citations_live(site.id, decision.citations)
            timings["liveness_check"] = (time.perf_counter_ns() - started) // 1_000_000
            if not live:
                decision = _safe_technical_failure(reason="stale_source")
        else:
            timings.setdefault("liveness_check", 0)
        conversation.active_generation_id = None
        started = time.perf_counter_ns()
        inserted = await self._persist_grounded_reply(conversation, decision)
        await self._session.commit()
        record_trace("decision", decision=decision, persisted=True)
        timings["commit"] = (time.perf_counter_ns() - started) // 1_000_000
        snapshot_id = None
        if decision.citations and decision.citations[0].snapshot_id is not None:
            snapshot_id = str(decision.citations[0].snapshot_id)
        log.info(
            "grounded_turn",
            conversation_id=str(conversation_id),
            generation_id=str(generation_id),
            site_id=str(site_id),
            snapshot_id=snapshot_id,
            request_id=decision.request_id,
            outcome=decision.outcome.value if decision.outcome is not None else None,
            reason=decision.reason_code,
            citation_count=len(decision.citations),
            stage_timings=dict(timings),
        )
        return CommandResult(conversation=conversation, site_key=site_key, message=inserted)

    async def _persist_grounded_reply(
        self, conversation: Conversation, decision: ResponseDecision
    ) -> Message:
        citations = decision.citations
        if citations:
            conversation.state = _transition(conversation.state, "bot_reply")
        chips = visitor_citation_payloads(citations=citations) if citations else []
        inserted = await self._insert_message(
            conversation,
            "bot",
            decision.body,
            source_chunk_ids=list(dict.fromkeys(c.chunk_id for c in citations))
            if citations
            else None,
            snapshot_id=citations[0].snapshot_id if citations else None,
            system_reason=self._system_reason_for(decision),
            source_urls=[str(chip["source_url"]) for chip in chips if chip["source_url"]]
            if citations
            else None,
            source_title=chips[0]["source_title"] if chips else None,
            response_outcome=decision.outcome.value if decision.outcome is not None else None,
            response_reason_code=decision.reason_code,
        )
        for citation in citations:
            self._session.add(
                MessageCitation(
                    message=inserted,
                    site_id=conversation.site_id,
                    chunk_id=citation.chunk_id,
                    snapshot_id=citation.snapshot_id,
                    response_start=citation.response_start,
                    response_end=citation.response_end,
                    source_start=citation.source_start,
                    source_end=citation.source_end,
                    cited_text=citation.cited_text,
                    source_title=citation.source_title,
                    source_url=citation.source_url,
                )
            )
        if decision.outcome is ResponseOutcome.SYNTHESIZED_ANSWER:
            conversation.fallback_count = 0
        elif (
            decision.reason_code in {"no_evidence", "grounding_reject", "needs_confirmation"}
            or decision.outcome is ResponseOutcome.CLARIFICATION
        ):
            conversation.fallback_count += 1
        elif decision.reason_code == "off_topic":
            conversation.fallback_count = 0
        if decision.offer_handoff and decision.outcome in {
            ResponseOutcome.KNOWLEDGE_GAP,
            ResponseOutcome.PARTIAL_ANSWER,
            ResponseOutcome.BOUNDARY,
            ResponseOutcome.SYNTHESIZED_ANSWER,
            None,
        }:
            # Persist the offer as bot speech; consent on the next visitor turn.
            conversation.fallback_count = max(conversation.fallback_count, 1)
        return inserted

    @staticmethod
    def _system_reason_for(decision: ResponseDecision) -> str:
        if decision.outcome is ResponseOutcome.CLARIFICATION:
            return "clarify"
        if decision.reason_code == "source_followup":
            return "answer"
        if decision.reason_code == "tech_fail" or (
            decision.provider_status is ProviderStatus.TECH_FAIL
        ):
            return "tech_fail"
        if (
            decision.reason_code == "grounding_reject"
            or decision.outcome is ResponseOutcome.PARTIAL_ANSWER
        ):
            return "insufficient"
        if decision.citations:
            return "answer"
        if decision.outcome is ResponseOutcome.BOUNDARY:
            return "policy_boundary"
        return "insufficient"

    async def _grounded_citations_live(self, site_id: UUID, citations: list[Citation]) -> bool:
        cited_chunk_ids = sorted(set(citation.chunk_id for citation in citations))
        if not cited_chunk_ids:
            return True
        result = await self._session.execute(
            live_chunks_query(site_id)
            .with_only_columns(KbChunk.id, KbChunk.snapshot_id, KbChunk.site_id)
            .where(KbChunk.id.in_(cited_chunk_ids))
            .order_by(KbChunk.id)
            .with_for_update(read=True, of=[KbChunk, KbPage, KbSource, KbSnapshot])
        )
        rows = result.all()
        by_id = {row.id: row for row in rows}
        if set(cited_chunk_ids) - set(by_id):
            return False
        citation_by_chunk = {citation.chunk_id: citation for citation in citations}
        for chunk_id, row in by_id.items():
            if row.site_id != site_id:
                return False
            citation = citation_by_chunk.get(chunk_id)
            if citation is None or row.snapshot_id != citation.snapshot_id:
                return False
        return True

    async def _release_generation(self, conversation_id: UUID, generation_id: UUID) -> None:
        try:
            await self._session.rollback()
            conversation, _site = await self._lock_site_then_conversation(conversation_id)
            if conversation is None or conversation.active_generation_id != generation_id:
                await self._session.commit()
                return
            conversation.active_generation_id = None
            await self._session.commit()
        except Exception:
            log.info(
                "bot_turn_unlock_failed",
                conversation_id=str(conversation_id),
                role="bot",
                length=0,
            )

    async def _latest_visitor_body(self, conversation_id: UUID) -> str:
        return await self._messages.latest_visitor_body(conversation_id)

    async def _lock_finalize_context(
        self, conversation_id: UUID, site_id: UUID
    ) -> tuple[Conversation | None, Site | None, str]:
        conversation, site = await self._lock_site_then_conversation(
            conversation_id, site_id=site_id
        )
        if conversation is None:
            return None, None, ""
        site_key = site.key if site is not None else ""
        return conversation, site, site_key

    async def _lock_site_then_conversation(
        self, conversation_id: UUID, *, site_id: UUID | None = None
    ) -> tuple[Conversation | None, Site | None]:
        resolved_site_id = site_id
        if resolved_site_id is None:
            probe = await self._conversations.get_by_id(conversation_id)
            if probe is None:
                return None, None
            resolved_site_id = probe.site_id
        site = await self._sites.lock_by_id(resolved_site_id)
        if site is None:
            return None, None
        cached = await self._conversations.get_by_id(conversation_id)
        if cached is not None:
            self._session.expire(cached)
        conversation = await self._conversations.lock_by_id(conversation_id)
        return conversation, site

    async def replay(
        self, conversation_id: UUID, cursor: int | None
    ) -> tuple[list[Message], Conversation]:
        conversation = await self._conversations.get_by_id(conversation_id)
        if conversation is None:
            raise CommandError("invalid")
        if cursor is None:
            return [], conversation
        messages = await self._messages.list_after(conversation_id, cursor)
        return messages, conversation

    async def assigned_agent_view(self, conversation: Conversation) -> dict | None:
        if conversation.assigned_agent_id is None:
            return None
        user = await self._users.get_by_id(conversation.assigned_agent_id)
        if user is None:
            return None
        return {"id": str(user.id), "display_name": user.display_name}

    async def parent_origin_allowed(self, site_id: UUID, parent_origin: str) -> bool:
        site = await self._sites.get_by_id(site_id)
        if site is None:
            return False
        return parent_origin in site.allowed_origins

    def _require_allowlisted_origin(self, origin_header: str | None, allowed: list[str]) -> str:
        if origin_header is None or origin_header == "null":
            raise CommandError("forbidden")
        try:
            origin = canonicalize_origin(origin_header)
        except InvalidOrigin as exc:
            raise CommandError("forbidden") from exc
        if origin not in allowed:
            raise CommandError("forbidden")
        return origin

    async def _resolve_visitor(
        self,
        site_id: UUID,
        resume_token: str | None,
        ip: str | None,
        user_agent: str | None,
        *,
        create_if_missing: bool,
    ) -> tuple[Visitor, str | None, bool]:
        if resume_token:
            found = await self._visitors.get_by_resume_hash(
                site_id, hash_resume_token(resume_token)
            )
            if found is not None:
                location = found.location
                if str(found.ip) != ip:
                    location = None
                    found.location_checked_at = None
                found.ip = ip
                found.user_agent = user_agent
                found.location = location
                await self._session.flush()
                return found, None, True
        if not create_if_missing:
            raise CommandError("not_found")
        token, token_hash = issue_resume_token()
        await self._rate_limit_create(ip, site_id)
        visitor = await self._visitors.create(
            site_id,
            token_hash,
            ip=ip,
            user_agent=user_agent,
            location=None,
        )
        return visitor, token, False

    async def _forget_visitor(self, site_id: UUID, resume_token: str | None) -> None:
        if not resume_token:
            return
        visitor = await self._visitors.lock_by_resume_hash(site_id, hash_resume_token(resume_token))
        if visitor is None:
            return
        _, replacement_hash = issue_resume_token()
        visitor.resume_token_hash = replacement_hash

    async def _reset_current_conversation(self, site_id: UUID, visitor_id: UUID) -> None:
        await self._visitors.lock_by_id(visitor_id)
        current = await self._conversations.get_open_for_visitor(
            site_id, visitor_id, for_update=True
        )
        if current is not None:
            current.state = _transition(current.state, "end")
            current.closed_at = datetime.now(UTC)
            current.active_generation_id = None
            if current.prechat_submission_id is not None:
                await self._insert_message(current, "system", RESET_LINE)
                self._bootstrap_wakeups.append(current)
            await self._session.flush()

    async def open_submitted_conversation_id(self, site_id: UUID, visitor_id: UUID) -> UUID | None:
        current = await self._conversations.get_open_for_visitor(site_id, visitor_id)
        if current is None:
            return None
        if current.state == "prechat" and current.prechat_submission_id is None:
            return None
        return current.id

    async def _refresh_conversation(
        self,
        site: Site,
        visitor: Visitor,
        conversation_id: UUID,
    ) -> Conversation:
        await self._visitors.lock_by_id(visitor.id)
        conversation = await self._conversations.lock_for_visitor(
            site.id, visitor.id, conversation_id
        )
        if conversation is None:
            raise CommandError("not_found")
        return conversation

    async def _resume_conversation(
        self,
        site: Site,
        visitor: Visitor,
        conversation_id: UUID,
        *,
        replace_current: bool,
    ) -> Conversation:
        await self._visitors.lock_by_id(visitor.id)
        target = await self._conversations.lock_for_visitor(site.id, visitor.id, conversation_id)
        if target is None:
            raise CommandError("not_found")
        current = await self._conversations.get_open_for_visitor(
            site.id, visitor.id, for_update=True
        )
        if target.state != "closed":
            if current is None or current.id != target.id:
                raise CommandError("not_found")
            return target
        if current is not None and current.id != target.id:
            draft_only = current.state == "prechat" and current.prechat_submission_id is None
            if not replace_current and not draft_only:
                raise CommandError("active_chat_exists")
            current.state = _transition(current.state, "end")
            current.closed_at = datetime.now(UTC)
            current.active_generation_id = None
            if current.prechat_submission_id is not None:
                await self._insert_message(current, "system", RESET_LINE)
                self._bootstrap_wakeups.append(current)
            # Release the partial unique index before reopening the selected row.
            await self._session.flush()

        target.state = _transition(target.state, "resume")
        target.assigned_agent_id = None
        target.active_generation_id = None
        target.closed_at = None
        target.fallback_count = 0
        target.attention_needed = False
        target.escalation_reason = None
        await self._insert_message(target, "system", RESUMED_LINE)
        self._bootstrap_wakeups.append(target)
        if not site.bot_enabled:
            await self._enter_callback(target)
        return target

    async def _open_or_create_conversation(self, site_id: UUID, visitor_id: UUID) -> Conversation:
        await self._visitors.lock_by_id(visitor_id)
        existing = await self._conversations.get_open_for_visitor(
            site_id, visitor_id, for_update=True
        )
        if existing is not None:
            return existing
        try:
            return await self._conversations.create(
                site_id, visitor_id, _transition(None, "start_prechat")
            )
        except IntegrityError:
            await self._session.rollback()
            recovered = await self._conversations.get_open_for_visitor(site_id, visitor_id)
            if recovered is None:
                raise
            return recovered

    async def _lock_or_open_visitor_conversation(
        self,
        conversation_id: UUID | None,
        visitor_id: UUID,
        parent_origin: str,
        pending_hello: tuple[str, str | None, str | None] | None,
    ) -> tuple[Conversation, str]:
        if conversation_id is not None:
            conversation, site_key = await self._lock_visitor_conversation(
                conversation_id, visitor_id, parent_origin
            )
        else:
            visitor = await self._visitors.lock_by_id(visitor_id)
            if visitor is None:
                raise CommandError("invalid")
            site = await self._sites.get_by_id(visitor.site_id)
            if site is None:
                raise CommandError("invalid")
            if parent_origin not in site.allowed_origins:
                raise CommandError("origin_revoked")
            conversation = await self._open_or_create_conversation(site.id, visitor_id)
            site_key = site.key
        if pending_hello is not None:
            conversation.page_url, conversation.page_title, conversation.referrer = pending_hello
        return conversation, site_key

    async def _lock_visitor_conversation(
        self, conversation_id: UUID, visitor_id: UUID, parent_origin: str
    ) -> tuple[Conversation, str]:
        conversation, site = await self._lock_site_then_conversation(conversation_id)
        if conversation is None or site is None or conversation.visitor_id != visitor_id:
            raise CommandError("invalid")
        if parent_origin not in site.allowed_origins:
            raise CommandError("origin_revoked")
        return conversation, site.key

    async def _lock_staff_conversation(self, conversation_id: UUID) -> tuple[Conversation, str]:
        conversation, site = await self._lock_site_then_conversation(conversation_id)
        if conversation is None or site is None:
            raise CommandError("invalid")
        return conversation, site.key

    async def _insert_message(
        self,
        conversation: Conversation,
        role: str,
        body: str,
        client_message_id: UUID | None = None,
        author_user_id: UUID | None = None,
        source_article_ids: list[UUID] | None = None,
        source_chunk_ids: list[UUID] | None = None,
        snapshot_id: UUID | None = None,
        system_reason: str | None = None,
        source_urls: list[str] | None = None,
        display_locator: str | None = None,
        source_title: str | None = None,
        response_outcome: str | None = None,
        response_reason_code: str | None = None,
        at: datetime | None = None,
        created_at: datetime | None = None,
        touch_last_message: bool = True,
    ) -> Message:
        message = await self._messages.create(
            conversation.id,
            conversation.site_id,
            role,
            body,
            client_message_id=client_message_id,
            author_user_id=author_user_id,
            source_article_ids=source_article_ids,
            source_chunk_ids=source_chunk_ids,
            snapshot_id=snapshot_id,
            system_reason=system_reason,
            source_urls=source_urls,
            display_locator=display_locator,
            source_title=source_title,
            response_outcome=response_outcome,
            response_reason_code=response_reason_code,
            created_at=created_at,
        )
        if touch_last_message:
            conversation.last_message_at = at or datetime.now(UTC)
        return message

    async def _rate_limit_submit(
        self, site_id: UUID, visitor_id: UUID, client_ip: str | None
    ) -> None:
        try:
            await RateLimiter().hit_visitor_submit(str(site_id), str(visitor_id), client_ip)
        except RateLimitExceeded as exc:
            raise CommandError("rate_limited") from exc
        except RateLimitUnavailable as exc:
            raise CommandError("unavailable") from exc

    async def _rate_limit_create(self, ip: str | None, site_id: UUID) -> None:
        try:
            await RateLimiter().hit_visitor_create(ip, str(site_id))
        except RateLimitExceeded as exc:
            raise CommandError("rate_limited") from exc
        except RateLimitUnavailable as exc:
            raise CommandError("unavailable") from exc
