"""Read-only inbox and submission views. Never commits or invokes a provider."""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.display_citations import visitor_citation_payloads
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.site import Site
from app.models.user import User
from app.models.visitor import Visitor
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.services.conversation_types import CommandError
from app.settings import get_settings

PREVIEW_MAX = 80
INBOX_PAGE = 50
INBOX_STATES = frozenset({"bot", "queued", "human", "closed"})
SUBMISSIONS_PAGE = 50


class ConversationQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._conversations = ConversationRepository(session)
        self._messages = MessageRepository(session)

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

    async def list_submissions(self, offset: int, limit: int | None) -> tuple[list[dict], bool]:
        page_size = SUBMISSIONS_PAGE if limit is None else min(max(limit, 1), SUBMISSIONS_PAGE)
        start = max(offset, 0)
        rows = await self._conversations.list_submissions(
            offset=start,
            limit=page_size + 1,
        )
        extra = rows[page_size:]
        page = rows[:page_size]
        items = [
            _submission_item(conversation, visitor, site, agent, opening)
            for conversation, visitor, site, agent, opening in page
        ]
        return items, bool(extra)

    async def get_inbox_detail(
        self, conversation_id: UUID, *, before_id: int | None = None
    ) -> dict:
        packed = await self._conversations.get_inbox_detail(conversation_id)
        if packed is None:
            raise CommandError("not_found")
        conversation, visitor, site, agent = packed
        limit = get_settings().message_replay_limit
        rows = await self._messages.list_for_conversation_with_authors_bounded(
            conversation.id, limit=limit + 1, before_id=before_id
        )
        has_older = len(rows) > limit
        if has_older:
            rows = rows[1:]
        oldest_id = rows[0][0].id if rows else None
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
                "location": visitor.location,
            },
            "page": {
                "title": conversation.page_title,
                "url": conversation.page_url,
                "referrer": conversation.referrer,
            },
            "messages": [self._inbox_message(message, author) for message, author in rows],
            "has_older": has_older,
            "older_before_id": oldest_id if has_older else None,
        }

    @staticmethod
    def _inbox_message(message: Message, author_user: User | None = None) -> dict:
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
            "display_locator": None,
            "source_title": message.source_title,
            "system_reason": message.system_reason,
            "created_at": created,
            "citations": visitor_citation_payloads(
                citations=list(message.citations or []),
                source_urls=list(message.source_urls) if message.source_urls is not None else None,
                source_title=message.source_title,
            ),
        }


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
            "location": visitor.location,
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
