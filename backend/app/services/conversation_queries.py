"""Read-only inbox and submission views. Never commits or invokes a provider."""

import csv
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, date, datetime, timedelta
from io import StringIO
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
from app.repositories.visitor_block_repo import VisitorBlockRepository
from app.services.conversation_types import CommandError
from app.settings import get_settings

PREVIEW_MAX = 80
INBOX_PAGE = 50
INBOX_STATES = frozenset({"bot", "queued", "human", "closed"})
SUBMISSIONS_PAGE = 50
EXPORT_MAX = 10_000
EXPORTABLE_COLUMNS = (
    "Name",
    "Email",
    "Phone",
    "Inquiry",
    "Intent",
    "State",
    "Site",
    "Site key",
    "Opening message",
    "Page title",
    "Page URL",
    "Referrer",
    "IP",
    "Location",
    "User agent",
    "Country",
    "Region",
    "Attention",
    "Assigned",
    "Visitor since",
    "Chat started",
    "Last message",
    "Closed",
)
STATE_LABEL = {
    "prechat": "Prechat",
    "bot": "Bot",
    "queued": "Needs Attention",
    "human": "Live",
    "closed": "Closed",
}


class ConversationQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._conversations = ConversationRepository(session)
        self._messages = MessageRepository(session)
        self._blocks = VisitorBlockRepository(session)

    async def list_inbox(
        self, state: str | None, cursor: str | None, site_id: UUID | None = None
    ) -> tuple[list[dict], str | None, dict[str, int], list[dict]]:
        filter_state = _inbox_state(state)
        cursor_ts, cursor_id = _decode_inbox_cursor(cursor)
        sites = [
            {"id": str(site.id), "name": site.name, "queued": queued}
            for site, queued in await self._conversations.list_inbox_sites()
        ]
        if site_id is not None and all(row["id"] != str(site_id) for row in sites):
            raise CommandError("invalid")
        rows = await self._conversations.list_inbox(
            state=filter_state,
            cursor_ts=cursor_ts,
            cursor_id=cursor_id,
            limit=INBOX_PAGE + 1,
            site_id=site_id,
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
        counts = await self._conversations.count_inbox_by_state(site_id)
        return items, next_cursor, counts, sites

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
            _submission_item(conversation, visitor, site, agent, opening, block_id)
            for conversation, visitor, site, agent, opening, block_id in page
        ]
        return items, bool(extra)

    async def export_submissions(
        self,
        columns: list[str],
        site_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
    ) -> str:
        if any(column not in EXPORTABLE_COLUMNS for column in columns):
            raise CommandError("unknown_column")
        created_from = (
            datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC)
            if date_from is not None
            else None
        )
        created_before = (
            datetime(date_to.year, date_to.month, date_to.day, tzinfo=UTC) + timedelta(days=1)
            if date_to is not None
            else None
        )
        rows = await self._conversations.list_submissions(
            offset=0,
            limit=EXPORT_MAX + 1,
            site_id=site_id,
            created_from=created_from,
            created_before=created_before,
        )
        if len(rows) > EXPORT_MAX:
            raise CommandError("export_too_large")
        buffer = StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        writer.writerow(columns)
        for conversation, visitor, site, agent, opening, block_id in rows:
            item = _submission_item(conversation, visitor, site, agent, opening, block_id)
            writer.writerow([_export_cell(column, item) for column in columns])
        return buffer.getvalue()

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
        matched = await self._blocks.find_matching(
            conversation.site_id,
            ip=str(visitor.ip) if visitor.ip is not None else None,
            email=visitor.email,
            phone=visitor.phone,
        )
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
            "blocked": matched is not None,
            "block_id": str(matched.id) if matched is not None else None,
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
        "site_id": str(site.id),
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
    block_id: UUID | None,
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
        "blocked": block_id is not None,
        "block_id": str(block_id) if block_id is not None else None,
    }


def _export_cell(column: str, item: dict) -> str:
    visitor = item["visitor"]
    page = item["page"]
    assigned = item["assigned_agent"]
    values: dict[str, object] = {
        "Name": visitor["name"],
        "Email": visitor["email"],
        "Phone": visitor["phone"],
        "Inquiry": item["inquiry_type"],
        "Intent": item["intent"],
        "State": STATE_LABEL.get(item["state"], item["state"]),
        "Site": item["site_name"],
        "Site key": item["site_key"],
        "Opening message": item["opening_message"],
        "Page title": page["title"],
        "Page URL": page["url"],
        "Referrer": page["referrer"],
        "IP": visitor["ip"],
        "Location": visitor["location"],
        "User agent": visitor["user_agent"],
        "Country": visitor["geo_country"],
        "Region": visitor["geo_region"],
        "Attention": "Yes" if item["attention_needed"] else "No",
        "Assigned": assigned["display_name"] if assigned else None,
        "Visitor since": visitor["created_at"],
        "Chat started": item["created_at"],
        "Last message": item["last_message_at"],
        "Closed": item["closed_at"],
    }
    value = values[column]
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value)
    # csv.writer escapes separators, but spreadsheets also interpret cell formulas.
    if text.lstrip().startswith(
        ("=", "+", "-", "@", "\uff1d", "\uff0b", "\uff0d", "\uff20")
    ) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text
