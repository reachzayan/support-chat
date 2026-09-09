from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from ipaddress import ip_address
from json import dumps
from secrets import token_bytes
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.outcome_copy import (
    DISENGAGE_LINE,
    KEEP_HELPING_LINE,
    OFF_TOPIC_LINE,
    is_transfer_offer_body,
    transfer_offer_line,
)
from app.chat.state_machine import IllegalTransition, apply_event
from app.llm.bot_responder import BotResponder, BufferedAnswer, output_is_safe
from app.llm.intent import (
    classify_intent,
    classify_sensitive,
    embed_intent_prototypes,
    intent_from_query_vector,
    is_chitchat,
    is_disengage_request,
    is_escalate_request,
    is_sensitive_request,
    is_transfer_consent,
    is_transfer_decline,
    is_unrelated_request,
)
from app.llm.safety_markers import OUTPUT_LEAK_MARKERS, SensitiveCategory
from app.models.conversation import INQUIRY_TYPES, Conversation
from app.models.message import Message
from app.models.site import Site
from app.models.user import User
from app.models.visitor import Visitor
from app.repositories.article_repo import ArticleRepository
from app.repositories.canned_reply_repo import CannedReplyRepository
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.kb_chunk_repo import KbChunkRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.origins import InvalidOrigin, canonicalize_origin, sanitize_visitor_url
from app.repositories.site_repo import SiteRepository
from app.repositories.user_repo import UserRepository
from app.repositories.visitor_repo import VisitorRepository
from app.services.faq_fastpath import normalize_fast_query, try_fast_answer
from app.services.full_context import answer_full_context, prior_provider_messages
from app.services.handoff_service import EscalationReason, HandoffService, HandoffTrigger
from app.services.kb_embedder import default_embedder
from app.services.kb_search import KbSearch
from app.services.off_topic import is_off_topic
from app.services.pii_redactor import redact_for_log
from app.services.rate_ceiling import RateCeiling
from app.services.rate_limit import RateLimiter, RateLimitExceeded, RateLimitUnavailable
from app.services.refusal_library import lookup_refusal
from app.services.route_decision import decide as decide_route
from app.services.route_decision import live_snapshots_for_site
from app.services.sufficiency import CitedUnit
from app.services.sufficiency import evaluate as evaluate_sufficiency
from app.settings import get_settings

log = structlog.get_logger("chat")

MAX_MESSAGE = 4000
MAX_NAME = 120
MAX_EMAIL = 320
MAX_PHONE = 40
MAX_TITLE = 300
MAX_URL = 2048
MAX_UA = 512
NOT_FOUND = "Not found"
PREVIEW_MAX = 80
INBOX_PAGE = 50
INBOX_STATES = frozenset({"bot", "queued", "human", "closed"})
SUBMISSIONS_PAGE = 200
ASSISTANT_LINE = "You're now chatting with the assistant."
CLOSED_BY_PREFIX = "This chat was closed by "
IDLE_TTL = timedelta(minutes=5)
OPEN_IDLE_STATES = frozenset({"prechat", "bot", "queued", "human"})
SENSITIVE_LINE = "Please do not share Social Security numbers or other screening identifiers."


class CommandError(Exception):
    def __init__(self, code: str, **extra: Any) -> None:
        self.code = code
        self.extra = extra
        super().__init__(code)


@dataclass
class CommandResult:
    conversation: Conversation
    site_key: str
    message: Message | None = None
    event: str = "message"
    client_message_id: str | None = None
    submission_id: str | None = None
    duplicate: bool = False
    generation_id: UUID | None = None


@dataclass
class BootstrapResult:
    site_name: str
    greeting: str
    privacy_url: str
    site_id: UUID
    visitor_id: UUID
    conversation_id: UUID
    parent_origin: str
    resume_token: str | None
    bot_enabled: bool
    human_enabled: bool


def _transition(state: str | None, event: str) -> str:
    try:
        return apply_event(state, event)
    except IllegalTransition as exc:
        raise CommandError("illegal_state") from exc


def hash_resume_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def prechat_payload_hash(
    name: str,
    email: str,
    phone: str,
    inquiry_type: str,
    message: str,
) -> str:
    payload = {
        "email": email,
        "inquiry_type": inquiry_type,
        "message": message,
        "name": name,
        "phone": phone,
    }
    return sha256(dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def peer_ip(host: str | None) -> str | None:
    if not host:
        return None
    try:
        return str(ip_address(host))
    except ValueError:
        return None


def cap_user_agent(raw: str | None) -> str | None:
    if raw is None:
        return None
    trimmed = raw.strip()
    if not trimmed:
        return None
    return trimmed[:MAX_UA]


def welcome_line(site_name: str, page_title: str | None) -> str:
    raw = (page_title or "").strip()
    title = raw.split("|", 1)[0].strip() if raw else ""
    brand = title or site_name
    return f"Hi, welcome to {brand}. How can we help you today?"


class ConversationService:
    def __init__(self, session: AsyncSession, responder=None, embedder=None) -> None:
        self._session = session
        self._sites = SiteRepository(session)
        self._visitors = VisitorRepository(session)
        self._conversations = ConversationRepository(session)
        self._messages = MessageRepository(session)
        self._users = UserRepository(session)
        self._canned = CannedReplyRepository(session)
        self._articles = ArticleRepository(session)
        self._chunks = KbChunkRepository(session)
        self._responder = responder if responder is not None else BotResponder()
        self._embedder = embedder if embedder is not None else default_embedder()
        self._intent_prototypes: dict[str, list[float]] | None = None
        self._pending_handoff_summary = None

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
                )
                await self._session.commit()
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
    ) -> BootstrapResult:
        site = await self._sites.get_by_key(site_key)
        if site is None or site.public_key != public_key or not site.enabled:
            raise CommandError("not_found")
        parent_origin = self._require_allowlisted_origin(origin_header, site.allowed_origins)
        visitor, issued_resume = await self._resolve_visitor(
            site.id, resume_token, peer_ip(client_host), cap_user_agent(user_agent)
        )
        conversation = await self._open_or_create_conversation(site.id, visitor.id)
        return BootstrapResult(
            site_name=site.name,
            greeting=site.greeting,
            privacy_url=site.privacy_url,
            site_id=site.id,
            visitor_id=visitor.id,
            conversation_id=conversation.id,
            parent_origin=parent_origin,
            resume_token=issued_resume,
            bot_enabled=site.bot_enabled,
            human_enabled=site.human_enabled,
        )

    async def hello(
        self,
        conversation_id: UUID,
        visitor_id: UUID,
        parent_origin: str,
        page_url: str,
        page_title: str,
        referrer: str,
    ) -> CommandResult:
        try:
            clean_url = sanitize_visitor_url(page_url, parent_origin, MAX_URL)
            clean_ref = ""
            if referrer:
                clean_ref = sanitize_visitor_url(referrer, parent_origin, MAX_URL)
        except InvalidOrigin as exc:
            raise CommandError("invalid") from exc
        title = (page_title or "").strip()[:MAX_TITLE]
        conversation, site_key = await self._lock_visitor_conversation(
            conversation_id, visitor_id, parent_origin
        )
        conversation.page_url = clean_url
        conversation.page_title = title or None
        conversation.referrer = clean_ref or None
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
        conversation_id: UUID,
        visitor_id: UUID,
        parent_origin: str,
        submission_id: UUID,
        name: str,
        email: str,
        phone: str,
        inquiry_type: str,
        message: str,
        client_ip: str | None = None,
    ) -> CommandResult:
        clean = self._normalize_prechat(name, email, phone, inquiry_type, message)
        conversation, site_key = await self._lock_visitor_conversation(
            conversation_id, visitor_id, parent_origin
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
        text = self._require_message_body(body)
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
        if await self._sites.get_by_id(conversation.site_id) is None:
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
            inserted = await self._insert_message(conversation, "system", KEEP_HELPING_LINE)
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
        text = self._require_message_body(body)
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
        conversation = await self._conversations.lock_by_id(conversation_id)
        if not self._idle_due(conversation, moment):
            await self._session.commit()
            return None
        site = await self._sites.get_by_id(conversation.site_id)
        site_key = site.key if site is not None else ""
        self._apply_idle_close(conversation, moment)
        await self._session.commit()
        return CommandResult(conversation=conversation, site_key=site_key, event="end")

    async def close_expired(
        self, now: datetime | None = None, limit: int = 100
    ) -> list[CommandResult]:
        moment = now or datetime.now(UTC)
        cutoff = moment - IDLE_TTL
        rows = await self._conversations.list_expired_open(cutoff, limit=limit)
        results: list[CommandResult] = []
        for conversation in rows:
            if not self._idle_due(conversation, moment):
                continue
            site = await self._sites.get_by_id(conversation.site_id)
            site_key = site.key if site is not None else ""
            self._apply_idle_close(conversation, moment)
            results.append(CommandResult(conversation=conversation, site_key=site_key, event="end"))
        await self._session.commit()
        return results

    def _idle_due(self, conversation: Conversation | None, moment: datetime) -> bool:
        if conversation is None or conversation.state not in OPEN_IDLE_STATES:
            return False
        if conversation.active_generation_id is not None:
            return False
        last_at = conversation.last_message_at
        if last_at is None:
            return False
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=UTC)
        return moment - last_at >= IDLE_TTL

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
        HandoffService(self._session).schedule_summary(row)

    async def _arm_bot_turn(self, conversation: Conversation, site: Site, text: str) -> UUID | None:
        if not site.bot_enabled:
            if conversation.state == "bot":
                await self._enter_callback(conversation)
            return None
        if conversation.state != "bot":
            return None
        conversation.intent = classify_intent(text)
        category = classify_sensitive(text)
        if category is not SensitiveCategory.NONE:
            log.info(
                "sensitive_intent",
                conversation_id=str(conversation.id),
                category=category.value,
                preview=redact_for_log(text),
            )
            await self._commit_sensitive_refusal(conversation, site, category)
            return None
        if is_disengage_request(text):
            log.info(
                "visitor_disengage",
                conversation_id=str(conversation.id),
                preview=redact_for_log(text),
            )
            await self._commit_disengage(conversation)
            return None
        if await self._handle_transfer_consent_reply(conversation, text):
            return None
        if is_escalate_request(text):
            conversation.active_generation_id = None
            await self._insert_message(conversation, "system", KEEP_HELPING_LINE)
            return None
        if is_chitchat(text):
            conversation.active_generation_id = None
            return None
        if is_unrelated_request(text, evidence_tokens=await self._evidence_tokens(site)):
            log.info(
                "visitor_off_topic",
                conversation_id=str(conversation.id),
                preview=redact_for_log(text),
            )
            await self._commit_off_topic(conversation)
            return None
        generation_id = uuid4()
        conversation.active_generation_id = generation_id
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

    async def _commit_disengage(self, conversation: Conversation) -> None:
        conversation.active_generation_id = None
        await self._insert_message(
            conversation, "system", DISENGAGE_LINE, system_reason="policy_boundary"
        )

    async def _commit_off_topic(self, conversation: Conversation) -> None:
        conversation.active_generation_id = None
        await self._insert_message(
            conversation, "system", OFF_TOPIC_LINE, system_reason="off_topic"
        )

    async def _evidence_tokens(self, site: Site) -> set[str]:
        from app.services.full_context import load_approved_units
        from app.services.kb_tokens import tokenize

        snapshots = await live_snapshots_for_site(self._session, site.id)
        if not snapshots:
            return set()
        units = await load_approved_units(self._session, [item.id for item in snapshots])
        tokens: set[str] = set()
        for unit in units:
            blob = " ".join(
                part
                for part in (unit.canonical_question, unit.heading, unit.answer_verbatim)
                if part
            )
            tokens.update(tokenize(blob))
        return tokens

    async def _awaiting_transfer_consent(self, conversation_id: UUID) -> bool:
        recent = await self._messages.list_recent_roles(
            conversation_id, {"visitor", "bot", "system", "agent"}, 2
        )
        if len(recent) < 2:
            return False
        prior = recent[-2]
        return prior.role == "system" and is_transfer_offer_body(prior.body)

    async def _latest_offered_question(self, conversation_id: UUID) -> str:
        recent = await self._messages.list_recent_roles(conversation_id, {"visitor"}, 2)
        if len(recent) >= 2:
            return recent[-2].body
        return await self._latest_visitor_body(conversation_id)

    async def _commit_sensitive_refusal(
        self, conversation: Conversation, site: Site, category: SensitiveCategory
    ) -> None:
        refusal = await lookup_refusal(self._session, site.id, category)
        body = refusal.body if refusal is not None else SENSITIVE_LINE
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
            )
        else:
            await self._insert_message(conversation, "system", body, system_reason="sensitive")
        await self._insert_message(
            conversation,
            "system",
            transfer_offer_line(human_enabled=site.human_enabled),
            system_reason="insufficient",
        )

    async def run_bot_turn(
        self, conversation_id: UUID, generation_id: UUID
    ) -> CommandResult | None:
        try:
            return await self._run_bot_turn(conversation_id, generation_id)
        except Exception:
            log.info("bot_turn_failed", conversation_id=str(conversation_id), role="bot", length=0)
            await self._release_generation(conversation_id, generation_id)
            return None

    async def _run_bot_turn(
        self, conversation_id: UUID, generation_id: UUID
    ) -> CommandResult | None:
        import time

        turn_started = time.perf_counter()
        conversation = await self._conversations.get_by_id(conversation_id)
        if conversation is None or conversation.state != "bot":
            return None
        if conversation.active_generation_id != generation_id:
            return None
        site = await self._sites.get_by_id(conversation.site_id)
        if site is None:
            return None
        if not site.bot_enabled:
            return await self._finalize_bot_turn(conversation_id, generation_id, site.id, None)

        visitor_text = await self._latest_visitor_body(conversation_id)
        route = await decide_route(
            self._session,
            site_id=site.id,
            visitor_text=visitor_text,
            intent=conversation.intent,
            sensitive=is_sensitive_request(visitor_text),
            escalate=is_escalate_request(visitor_text),
        )
        route_timings = {"intent_ms": int(route.elapsed_ms)}
        if route.fast_path_ms is not None:
            route_timings["fast_path_ms"] = int(route.fast_path_ms)
        log.info(
            "bot_route",
            conversation_id=str(conversation_id),
            path=route.path,
            reason=route.reason,
            token_estimate=route.token_estimate,
        )
        early_stop, early_result = await self._handle_early_route(
            conversation_id, generation_id, site, route, visitor_text, route_timings
        )
        if early_stop:
            return early_result

        if await self._is_off_topic_turn(site, visitor_text):
            log.info(
                "off_topic",
                conversation_id=str(conversation_id),
                blocklist_hit=True,
            )
            return await self._finalize_bot_turn(
                conversation_id,
                generation_id,
                site.id,
                None,
                system_reason="off_topic",
                outcome_reason="off_topic",
                stage_timings=route_timings,
            )

        try:
            if not await RateCeiling().allow(conversation_id):
                return await self._finalize_bot_turn(
                    conversation_id,
                    generation_id,
                    site.id,
                    None,
                    system_reason="rate_ceiling",
                    outcome_reason="rate_ceiling",
                    provider_status="rate_limited",
                    stage_timings=route_timings,
                )
        except RateLimitUnavailable:
            log.info("rate_ceiling_unavailable", conversation_id=str(conversation_id))

        route_path = self._resolved_generation_path(route)
        window = await self._messages.list_recent_roles(
            conversation_id, {"visitor", "bot"}, get_settings().conversation_window_size
        )
        answer, hits, provider_error, path_timings = await self._generate_for_path(
            site, route, route_path, visitor_text, window, conversation
        )
        return await self._finalize_from_sufficiency(
            conversation_id,
            generation_id,
            site,
            visitor_text,
            answer,
            hits,
            provider_error,
            turn_started,
            prior_timings={**route_timings, **path_timings},
        )

    async def _is_off_topic_turn(self, site: Site, visitor_text: str) -> bool:
        blocklist = list(getattr(site, "off_brand_blocklist", None) or [])
        if not blocklist:
            return False
        snapshots = await live_snapshots_for_site(self._session, site.id)
        snapshot_ids = [item.id for item in snapshots]
        if not snapshot_ids:
            return is_off_topic(visitor_text, blocklist=blocklist, evidence_bodies=[])
        from app.services.full_context import load_approved_units

        units = await load_approved_units(self._session, snapshot_ids)
        bodies = [
            " ".join(
                part
                for part in (
                    unit.canonical_question or "",
                    unit.heading or "",
                    unit.answer_verbatim or "",
                )
                if part
            )
            for unit in units
            if unit.legal_sensitive is False
        ]
        hit = is_off_topic(visitor_text, blocklist=blocklist, evidence_bodies=bodies)
        if hit:
            log.info(
                "off_topic",
                conversation_id=None,
                site_id=str(site.id),
                blocklist_hit=True,
            )
        return hit

    async def _handle_early_route(
        self,
        conversation_id: UUID,
        generation_id: UUID,
        site: Site,
        route,
        visitor_text: str,
        stage_timings: dict[str, int] | None = None,
    ) -> tuple[bool, CommandResult | None]:
        if route.path in {"escalate", "sensitive"}:
            locked = await self._conversations.lock_by_id(conversation_id)
            if locked is not None and locked.active_generation_id == generation_id:
                locked.active_generation_id = None
                await self._session.commit()
                return True, CommandResult(conversation=locked, site_key=site.key)
            await self._session.commit()
            return True, None
        if route.path != "fast":
            return False, None
        normalized = normalize_fast_query(visitor_text)
        if normalized is None:
            return False, None
        fast = await try_fast_answer(self._session, site.id, list(route.snapshot_ids), normalized)
        if fast is None:
            return False, None
        answer = BufferedAnswer(
            body=fast.answer_verbatim,
            source_chunk_ids=[fast.unit_id],
            accepted=True,
            source_urls=[fast.page_url],
            snapshot_id=fast.snapshot_id,
            display_locator=fast.display_locator,
            source_title=fast.source_title,
        )
        result = await self._finalize_bot_turn(
            conversation_id,
            generation_id,
            site.id,
            answer,
            system_reason="answer",
            stage_timings=stage_timings,
        )
        return True, result

    def _resolved_generation_path(self, route) -> str:
        if route.path != "fast":
            return route.path
        if route.token_estimate < get_settings().full_context_max_tokens:
            return "full_context"
        return "hybrid"

    async def _generate_for_path(
        self,
        site: Site,
        route,
        route_path: str,
        visitor_text: str,
        window: list[Message],
        conversation: Conversation,
    ) -> tuple[BufferedAnswer | None, list, bool, dict[str, int]]:
        if route_path == "full_context":
            return await self._generate_full_context(site, route, visitor_text, window)
        return await self._generate_hybrid(site, visitor_text, window, conversation)

    async def _generate_full_context(
        self, site: Site, route, visitor_text: str, window: list[Message]
    ) -> tuple[BufferedAnswer | None, list, bool, dict[str, int]]:
        import time

        prep_started = time.perf_counter()
        provider_error = False
        try:
            answer = await answer_full_context(
                self._session,
                site,
                list(route.snapshot_ids),
                window,
                visitor_text,
                responder=self._responder,
            )
        except Exception as exc:
            provider_error = True
            log.info(
                "provider_failure",
                conversation_id=None,
                error_class=type(exc).__name__,
                elapsed_ms=0,
            )
            answer = BufferedAnswer("", [], False)
        model_ms = round((time.perf_counter() - prep_started) * 1000)
        log.info(
            "full_context_stage",
            elapsed_ms=model_ms,
        )
        hits: list = []
        if answer is not None:
            for chunk_id in answer.source_chunk_ids or []:
                found = await self._chunks.get_enabled_for_site(site.id, chunk_id)
                if found is not None:
                    hits.append(found)
            lowered = (answer.body or "").casefold()
            if answer.accepted and any(marker in lowered for marker in OUTPUT_LEAK_MARKERS):
                answer = BufferedAnswer(
                    answer.body,
                    list(answer.source_chunk_ids or []),
                    False,
                    unsafe=True,
                    reject_reason="injection_leak",
                )
        return answer, hits, provider_error, {"model_ms": model_ms}

    async def _generate_hybrid(
        self,
        site: Site,
        visitor_text: str,
        window: list[Message],
        conversation: Conversation,
    ) -> tuple[BufferedAnswer | None, list, bool, dict[str, int]]:
        import time

        retrieval_started = time.perf_counter()
        query_vector = await self._embedder.embed_query(visitor_text)
        if query_vector is None:
            log.info(
                "embed_timeout",
                conversation_id=str(conversation.id),
                embed_timeout=True,
                role="bot",
                length=0,
            )
        if self._intent_prototypes is None and query_vector is not None:
            self._intent_prototypes = await embed_intent_prototypes(self._embedder)
        if query_vector is not None and self._intent_prototypes is not None:
            conversation.intent = intent_from_query_vector(query_vector, self._intent_prototypes)
            await self._session.flush()
        hits = await KbSearch(self._session).search(site.id, visitor_text, query_vector)
        await self._session.commit()
        retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000)
        model_started = time.perf_counter() if hits and self._responder is not None else None
        answer = await self._produce_answer(
            site,
            visitor_text,
            hits,
            prior_messages=prior_provider_messages(window, visitor_text),
        )
        provider_error = answer is None and bool(hits)
        path_timings: dict[str, int] = {"retrieval_ms": retrieval_ms}
        if model_started is not None:
            path_timings["model_ms"] = round((time.perf_counter() - model_started) * 1000)
        return answer, hits, provider_error, path_timings

    async def _finalize_from_sufficiency(
        self,
        conversation_id: UUID,
        generation_id: UUID,
        site: Site,
        visitor_text: str,
        answer: BufferedAnswer | None,
        hits: list,
        provider_error: bool,
        turn_started: float,
        prior_timings: dict[str, int] | None = None,
    ) -> CommandResult | None:
        import time

        cited_units = await self._cited_units_for_answer(site.id, answer, hits)
        live_urls = {unit.url for unit in cited_units if unit.url}
        sufficiency_started = time.perf_counter()
        if answer is not None and (answer.unsafe or answer.reject_reason):
            decision_reason = answer.reject_reason or "unsafe"
            log.info(
                "output_reject",
                reason=decision_reason,
                conversation_id=str(conversation_id),
            )
            if answer.unsafe and decision_reason == "injection_leak":
                system_reason = "disengage"
            elif answer.unsafe:
                system_reason = "policy_boundary"
            else:
                system_reason = "insufficient"
            return await self._finalize_bot_turn(
                conversation_id,
                generation_id,
                site.id,
                answer,
                system_reason=system_reason,
                outcome_reason=decision_reason,
                stage_timings={
                    **(prior_timings or {}),
                    "sufficiency_ms": round((time.perf_counter() - sufficiency_started) * 1000),
                    "turn_ms": round((time.perf_counter() - turn_started) * 1000),
                },
            )
        decision = evaluate_sufficiency(
            answer,
            cited_units=cited_units,
            live_urls=live_urls,
            provider_error=provider_error or (answer is None),
            visitor_sensitive=is_sensitive_request(visitor_text),
        )
        sufficiency_ms = round((time.perf_counter() - sufficiency_started) * 1000)
        log.info(
            "sufficiency",
            outcome=decision.outcome,
            reason=decision.reason,
            elapsed_ms=sufficiency_ms,
            turn_ms=round((time.perf_counter() - turn_started) * 1000),
        )
        if decision.outcome != "answer":
            log.info(
                "sufficiency_reject",
                conversation_id=str(conversation_id),
                reason=decision.reason,
                cited_count=len(cited_units),
            )
        if decision.reason == "no_citation":
            log.info("citation_reject", conversation_id=str(conversation_id))
        stage_timings = {
            **(prior_timings or {}),
            "sufficiency_ms": sufficiency_ms,
            "turn_ms": round((time.perf_counter() - turn_started) * 1000),
        }
        if decision.outcome == "answer" and answer is not None and answer.accepted:
            return await self._finalize_bot_turn(
                conversation_id,
                generation_id,
                site.id,
                answer,
                system_reason="answer",
                stage_timings=stage_timings,
            )
        if decision.outcome == "clarify" and decision.clarification:
            clarify = BufferedAnswer(
                body=decision.clarification,
                source_chunk_ids=[],
                accepted=False,
            )
            return await self._finalize_bot_turn(
                conversation_id,
                generation_id,
                site.id,
                clarify,
                system_reason="clarify",
                clarification=decision.clarification,
                stage_timings=stage_timings,
            )
        return await self._finalize_bot_turn(
            conversation_id,
            generation_id,
            site.id,
            answer,
            system_reason=decision.outcome,
            outcome_reason=decision.reason,
            stage_timings=stage_timings,
            provider_status="timeout" if decision.outcome == "tech_fail" else "ok",
            candidate_unit_ids=[unit.id for unit in cited_units],
            rejection_reasons=[
                {"unit_id": str(unit.id), "reason": decision.reason} for unit in cited_units
            ],
        )

    async def _cited_units_for_answer(
        self, site_id: UUID, answer: BufferedAnswer | None, hits: list
    ) -> list[CitedUnit]:
        units: list[CitedUnit] = []
        seen: set[UUID] = set()
        if answer is not None:
            for chunk_id in answer.source_chunk_ids or []:
                if chunk_id in seen:
                    continue
                seen.add(chunk_id)
                packed = await self._chunks.get_enabled_with_page(site_id, chunk_id)
                if packed is None:
                    units.append(
                        CitedUnit(
                            id=chunk_id,
                            answer_verbatim="",
                            url="",
                            enabled=False,
                            snapshot_live=False,
                        )
                    )
                    continue
                chunk, page = packed
                units.append(
                    CitedUnit(
                        id=chunk.id,
                        answer_verbatim=chunk.answer_verbatim,
                        url=page.url,
                        legal_sensitive=bool(chunk.legal_sensitive),
                        enabled=bool(chunk.enabled),
                        snapshot_live=True,
                    )
                )
        for hit in hits:
            chunk_id = getattr(hit, "id", None)
            if chunk_id is None or chunk_id in seen:
                continue
            seen.add(chunk_id)
            units.append(
                CitedUnit(
                    id=chunk_id,
                    answer_verbatim=getattr(hit, "answer_verbatim", None)
                    or getattr(hit, "body", "")
                    or "",
                    url=getattr(hit, "url", "") or "",
                    legal_sensitive=bool(getattr(hit, "legal_sensitive", False)),
                    enabled=True,
                    snapshot_live=True,
                )
            )
        return units

    async def _release_generation(self, conversation_id: UUID, generation_id: UUID) -> None:
        try:
            await self._session.rollback()
            conversation = await self._conversations.lock_by_id(conversation_id)
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

    async def _produce_answer(
        self,
        site: Site,
        visitor_text: str,
        hits: list,
        prior_messages: list[dict] | None = None,
    ) -> BufferedAnswer | None:
        if not hits or self._responder is None:
            return None
        try:
            if hasattr(self._responder, "generate_from_documents"):
                answer = await self._responder.generate_from_documents(
                    site=site,
                    visitor_text=visitor_text,
                    documents=hits,
                    prior_messages=prior_messages or [],
                )
            else:
                answer = await self._responder.generate(site, visitor_text, hits)
        except Exception as exc:
            log.info(
                "provider_failure",
                conversation_id=None,
                error_class=type(exc).__name__,
                elapsed_ms=0,
            )
            return None
        return self._gate_buffered_answer(site, answer, hits)

    def _gate_buffered_answer(
        self, site: Site, answer: BufferedAnswer, hits: list
    ) -> BufferedAnswer:
        allowed = [item.id for item in hits]
        cited = answer.source_chunk_ids or answer.source_article_ids
        blocklist = list(getattr(site, "off_brand_blocklist", None) or [])
        cited_text = "\n".join(
            str(getattr(item, "answer_verbatim", None) or getattr(item, "body", "") or "")
            for item in hits
            if getattr(item, "id", None) in set(cited)
        )
        if answer.accepted and output_is_safe(
            answer.body,
            allowed,
            cited,
            cited_answer_text=cited_text,
            off_brand_blocklist=blocklist,
        ):
            return answer
        if not answer.accepted and not answer.unsafe:
            return BufferedAnswer(
                answer.body,
                cited,
                False,
                reject_reason=getattr(answer, "reject_reason", None),
            )
        return BufferedAnswer(
            answer.body,
            cited,
            False,
            unsafe=True,
            reject_reason=getattr(answer, "reject_reason", None) or "unsafe",
        )

    async def _finalize_bot_turn(
        self,
        conversation_id: UUID,
        generation_id: UUID,
        site_id: UUID,
        answer: BufferedAnswer | None,
        *,
        system_reason: str | None = None,
        clarification: str | None = None,
        outcome_reason: str | None = None,
        stage_timings: dict[str, int] | None = None,
        provider_status: str = "ok",
        candidate_unit_ids: list[UUID] | None = None,
        rejection_reasons: list[dict] | None = None,
    ) -> CommandResult | None:
        conversation, site, site_key = await self._lock_finalize_context(
            conversation_id, generation_id, site_id
        )
        if conversation is None:
            return None
        if site is None:
            return CommandResult(conversation=conversation, site_key=site_key)
        if conversation.state != "bot" or conversation.active_generation_id != generation_id:
            await self._session.commit()
            return CommandResult(conversation=conversation, site_key=site_key)
        if not site.bot_enabled:
            handoff = await self._enter_callback(conversation, stage_timings=stage_timings)
            await self._commit_and_schedule()
            del handoff
            return CommandResult(conversation=conversation, site_key=site_key)
        return await self._commit_finalize_outcome(
            conversation,
            site,
            site_key,
            answer,
            system_reason,
            clarification,
            outcome_reason=outcome_reason,
            stage_timings=stage_timings,
            provider_status=provider_status,
            candidate_unit_ids=candidate_unit_ids,
            rejection_reasons=rejection_reasons,
        )

    async def _lock_finalize_context(
        self, conversation_id: UUID, generation_id: UUID, site_id: UUID
    ) -> tuple[Conversation | None, Site | None, str]:
        del generation_id
        cached = await self._conversations.get_by_id(conversation_id)
        if cached is not None:
            self._session.expire(cached)
        conversation = await self._conversations.lock_by_id(conversation_id)
        if conversation is None:
            return None, None, ""
        site = await self._sites.get_by_id(site_id)
        site_key = site.key if site is not None else ""
        return conversation, site, site_key

    async def _commit_finalize_outcome(
        self,
        conversation: Conversation,
        site: Site,
        site_key: str,
        answer: BufferedAnswer | None,
        system_reason: str | None,
        clarification: str | None,
        *,
        outcome_reason: str | None = None,
        stage_timings: dict[str, int] | None = None,
        provider_status: str = "ok",
        candidate_unit_ids: list[UUID] | None = None,
        rejection_reasons: list[dict] | None = None,
    ) -> CommandResult:
        if system_reason == "clarify" and clarification:
            return await self._commit_clarify(conversation, site_key, clarification)
        cited = [] if answer is None else (answer.source_chunk_ids or answer.source_article_ids)
        if system_reason == "answer" and answer is not None and answer.accepted and cited:
            if await self._sources_live(site.id, cited):
                return await self._commit_grounded(
                    conversation, site_key, answer, system_reason="answer"
                )
        if is_chitchat(await self._latest_visitor_body(conversation.id)):
            conversation.active_generation_id = None
            await self._session.commit()
            return CommandResult(conversation=conversation, site_key=site_key)
        if system_reason == "off_topic":
            return await self._commit_off_topic_finalize(conversation, site_key)
        if system_reason == "disengage":
            conversation.active_generation_id = None
            inserted = await self._insert_message(
                conversation, "system", DISENGAGE_LINE, system_reason="policy_boundary"
            )
            await self._session.commit()
            return CommandResult(conversation=conversation, site_key=site_key, message=inserted)
        return await self._commit_transfer_offer(conversation, site_key, site)

    async def _commit_clarify(
        self, conversation: Conversation, site_key: str, clarification: str
    ) -> CommandResult:
        conversation.active_generation_id = None
        conversation.fallback_count = 0
        inserted = await self._insert_message(
            conversation,
            "system",
            clarification,
            system_reason="clarify",
        )
        await self._session.commit()
        return CommandResult(conversation=conversation, site_key=site_key, message=inserted)

    async def _commit_off_topic_finalize(
        self, conversation: Conversation, site_key: str
    ) -> CommandResult:
        conversation.active_generation_id = None
        inserted = await self._insert_message(
            conversation, "system", OFF_TOPIC_LINE, system_reason="off_topic"
        )
        await self._session.commit()
        return CommandResult(conversation=conversation, site_key=site_key, message=inserted)

    async def _commit_transfer_offer(
        self, conversation: Conversation, site_key: str, site: Site | None = None
    ) -> CommandResult:
        if site is None:
            site = await self._sites.get_by_id(conversation.site_id)
        conversation.fallback_count += 1
        conversation.active_generation_id = None
        human_on = bool(site is not None and site.human_enabled)
        inserted = await self._insert_message(
            conversation,
            "system",
            transfer_offer_line(human_enabled=human_on),
            system_reason="insufficient",
        )
        await self._session.commit()
        return CommandResult(conversation=conversation, site_key=site_key, message=inserted)

    async def _sources_live(self, site_id: UUID, chunk_ids: list[UUID]) -> bool:
        if not chunk_ids:
            return False
        for chunk_id in chunk_ids:
            found = await self._chunks.get_enabled_for_site(site_id, chunk_id)
            if found is None:
                return False
        return True

    async def _commit_grounded(
        self,
        conversation: Conversation,
        site_key: str,
        answer: BufferedAnswer,
        *,
        system_reason: str = "answer",
    ) -> CommandResult:
        conversation.state = _transition(conversation.state, "bot_reply")
        conversation.fallback_count = 0
        conversation.active_generation_id = None
        cited = answer.source_chunk_ids or answer.source_article_ids
        snapshot_id = answer.snapshot_id or await self._snapshot_id_for_chunks(
            conversation.site_id, cited
        )
        inserted = await self._insert_message(
            conversation,
            "bot",
            answer.body,
            source_chunk_ids=cited,
            snapshot_id=snapshot_id,
            system_reason=system_reason,
            source_urls=answer.source_urls or None,
            display_locator=answer.display_locator,
            source_title=answer.source_title,
        )
        await self._session.commit()
        return CommandResult(conversation=conversation, site_key=site_key, message=inserted)

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

    async def list_inbox(
        self, state: str | None, cursor: str | None
    ) -> tuple[list[dict], str | None, dict[str, int]]:
        filter_state = _inbox_state(state)
        cursor_ts, cursor_id = _decode_inbox_cursor(cursor)
        rows = await self._conversations.list_inbox(
            state=filter_state,
            cursor_ts=cursor_ts,
            cursor_id=cursor_id,
            limit=INBOX_PAGE + 1,
        )
        extra = rows[INBOX_PAGE:]
        page = rows[:INBOX_PAGE]
        items = [
            _inbox_list_item(conversation, visitor, site, agent, preview)
            for conversation, visitor, site, agent, preview in page
        ]
        next_cursor = None
        if extra and page:
            last = page[-1][0]
            next_cursor = _encode_inbox_cursor(last.last_message_at, last.id)
        counts = await self._conversations.count_inbox_by_state()
        return items, next_cursor, counts

    async def list_submissions(self) -> list[dict]:
        rows = await self._conversations.list_submissions(limit=SUBMISSIONS_PAGE)
        return [
            _submission_item(conversation, visitor, site, agent, opening)
            for conversation, visitor, site, agent, opening in rows
        ]

    async def get_inbox_detail(self, conversation_id: UUID) -> dict:
        packed = await self._conversations.get_inbox_detail(conversation_id)
        if packed is None:
            raise CommandError("not_found")
        conversation, visitor, site, agent = packed
        rows = await self._messages.list_for_conversation_with_authors(conversation.id)
        return {
            "id": str(conversation.id),
            "site_id": str(site.id),
            "site_name": site.name,
            "state": conversation.state,
            "inquiry_type": conversation.inquiry_type,
            "intent": conversation.intent,
            "attention_needed": conversation.attention_needed,
            "escalation_reason": conversation.escalation_reason,
            "human_enabled": site.human_enabled,
            "bot_enabled": site.bot_enabled,
            "assigned_agent": _user_ref(agent),
            "visitor": {
                "name": visitor.name,
                "email": visitor.email,
                "phone": visitor.phone,
                "ip": str(visitor.ip) if visitor.ip is not None else None,
                "user_agent": visitor.user_agent,
            },
            "page": {
                "title": conversation.page_title,
                "url": conversation.page_url,
                "referrer": conversation.referrer,
            },
            "messages": [self._inbox_message(message, author) for message, author in rows],
        }

    async def list_canned_replies(self, site_id: UUID) -> list[dict]:
        replies = await self._canned.list_for_site(site_id)
        return [{"shortcut": reply.shortcut, "body": reply.body} for reply in replies]

    def _inbox_message(self, message: Message, author_user: User | None = None) -> dict:
        author = _user_ref(author_user) if author_user is not None else None
        source_ids = None
        if message.source_chunk_ids is not None:
            source_ids = [str(item) for item in message.source_chunk_ids]
        elif message.source_article_ids is not None:
            source_ids = [str(item) for item in message.source_article_ids]
        created = message.created_at
        return {
            "id": message.id,
            "role": message.role,
            "author_user": author,
            "body": message.body,
            "source_article_ids": source_ids,
            "source_chunk_ids": (
                [str(item) for item in message.source_chunk_ids]
                if message.source_chunk_ids is not None
                else None
            ),
            "source_urls": list(message.source_urls) if message.source_urls is not None else None,
            "display_locator": message.display_locator,
            "source_title": message.source_title,
            "system_reason": message.system_reason,
            "created_at": created,
        }

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
    ) -> tuple[Visitor, str | None]:
        if resume_token:
            found = await self._visitors.get_by_resume_hash(
                site_id, hash_resume_token(resume_token)
            )
            if found is not None:
                found.ip = ip
                found.user_agent = user_agent
                await self._session.flush()
                return found, None
        token, token_hash = _issue_resume_token()
        await self._rate_limit_create(ip, site_id)
        visitor = await self._visitors.create(site_id, token_hash, ip=ip, user_agent=user_agent)
        return visitor, token

    async def _open_or_create_conversation(self, site_id: UUID, visitor_id: UUID) -> Conversation:
        await self._visitors.lock_by_id(visitor_id)
        existing = await self._conversations.get_open_for_visitor(visitor_id, for_update=True)
        if existing is not None:
            return existing
        try:
            return await self._conversations.create(
                site_id, visitor_id, _transition(None, "start_prechat")
            )
        except IntegrityError:
            await self._session.rollback()
            recovered = await self._conversations.get_open_for_visitor(visitor_id)
            if recovered is None:
                raise
            return recovered

    async def _lock_visitor_conversation(
        self, conversation_id: UUID, visitor_id: UUID, parent_origin: str
    ) -> tuple[Conversation, str]:
        conversation = await self._conversations.lock_by_id(conversation_id)
        if conversation is None or conversation.visitor_id != visitor_id:
            raise CommandError("invalid")
        site = await self._sites.get_by_id(conversation.site_id)
        if site is None or parent_origin not in site.allowed_origins:
            raise CommandError("origin_revoked")
        return conversation, site.key

    async def _lock_staff_conversation(self, conversation_id: UUID) -> tuple[Conversation, str]:
        conversation = await self._conversations.lock_by_id(conversation_id)
        if conversation is None:
            raise CommandError("invalid")
        site = await self._sites.get_by_id(conversation.site_id)
        if site is None:
            raise CommandError("invalid")
        return conversation, site.key

    async def _snapshot_id_for_chunks(
        self, site_id: UUID, chunk_ids: list[UUID] | None
    ) -> UUID | None:
        if not chunk_ids:
            return None
        chunk = await self._chunks.get_enabled_for_site(site_id, chunk_ids[0])
        if chunk is None:
            return None
        return chunk.snapshot_id

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
        at: datetime | None = None,
    ) -> Message:
        message = await self._messages.create(
            conversation.id,
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
        )
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

    def _normalize_prechat(
        self, name: str, email: str, phone: str, inquiry_type: str, message: str
    ) -> dict[str, str]:
        clean_name = name.strip()
        clean_email = email.strip().lower()
        clean_phone = phone.strip()
        clean_message = message.strip()
        inquiry = inquiry_type.strip() if inquiry_type else "other"
        if not clean_name or not clean_email:
            raise CommandError("invalid")
        if (
            len(clean_name) > MAX_NAME
            or len(clean_email) > MAX_EMAIL
            or len(clean_phone) > MAX_PHONE
        ):
            raise CommandError("oversize")
        if len(clean_message) > MAX_MESSAGE:
            raise CommandError("oversize")
        if inquiry not in INQUIRY_TYPES:
            raise CommandError("invalid")
        if "@" not in clean_email or " " in clean_email:
            raise CommandError("invalid")
        return {
            "name": clean_name,
            "email": clean_email,
            "phone": clean_phone,
            "inquiry_type": inquiry,
            "message": clean_message,
        }

    def _require_message_body(self, body: str) -> str:
        text = body.strip()
        if not text:
            raise CommandError("invalid")
        if len(text) > MAX_MESSAGE:
            raise CommandError("oversize")
        return text


def _issue_resume_token() -> tuple[str, str]:
    raw = token_bytes(32)
    token = urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return token, hash_resume_token(token)


def _inbox_state(state: str | None) -> str | None:
    if state is None or state == "":
        return None
    if state not in INBOX_STATES:
        raise CommandError("invalid")
    return state


def _encode_inbox_cursor(ts: datetime, conversation_id: UUID) -> str:
    raw = f"{ts.isoformat()}|{conversation_id}"
    return urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_inbox_cursor(cursor: str | None) -> tuple[datetime | None, UUID | None]:
    if cursor is None or cursor == "":
        return None, None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        stamp, identifier = raw.split("|", 1)
        return datetime.fromisoformat(stamp), UUID(identifier)
    except (ValueError, UnicodeError) as exc:
        raise CommandError("invalid") from exc


def _visitor_display(visitor: Visitor) -> str:
    if visitor.name:
        return visitor.name
    if visitor.ip is not None:
        return str(visitor.ip)
    return "Visitor"


def _preview(body: str | None) -> str:
    if not body:
        return ""
    return body[:PREVIEW_MAX]


def _user_ref(user: User | None) -> dict | None:
    if user is None:
        return None
    return {"id": str(user.id), "display_name": user.display_name}


def _inbox_list_item(
    conversation: Conversation,
    visitor: Visitor,
    site: Site,
    agent: User | None,
    preview: str | None,
) -> dict:
    return {
        "id": str(conversation.id),
        "visitor_display": _visitor_display(visitor),
        "site_name": site.name,
        "state": conversation.state,
        "preview": _preview(preview),
        "last_message_at": conversation.last_message_at,
        "assigned_agent": _user_ref(agent),
    }


def _submission_item(
    conversation: Conversation,
    visitor: Visitor,
    site: Site,
    agent: User | None,
    opening: str | None,
) -> dict:
    return {
        "id": str(conversation.id),
        "site_id": str(site.id),
        "site_key": site.key,
        "site_name": site.name,
        "state": conversation.state,
        "inquiry_type": conversation.inquiry_type,
        "intent": conversation.intent,
        "attention_needed": conversation.attention_needed,
        "opening_message": opening,
        "assigned_agent": _user_ref(agent),
        "visitor": {
            "name": visitor.name,
            "email": visitor.email,
            "phone": visitor.phone,
            "ip": str(visitor.ip) if visitor.ip is not None else None,
            "user_agent": visitor.user_agent,
            "geo_country": visitor.geo_country,
            "geo_region": visitor.geo_region,
            "created_at": visitor.created_at,
        },
        "page": {
            "title": conversation.page_title,
            "url": conversation.page_url,
            "referrer": conversation.referrer,
        },
        "created_at": conversation.created_at,
        "last_message_at": conversation.last_message_at,
        "closed_at": conversation.closed_at,
    }
