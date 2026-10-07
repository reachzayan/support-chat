"""Bounded staff search. Literal substring matching; no visitor-supplied SQL syntax."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import String, and_, case, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_log import AppLog
from app.models.canned_reply import CannedReply
from app.models.conversation import Conversation
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_snapshot import KbSnapshot
from app.models.kb_source import KbSource
from app.models.knowledge_gap import KnowledgeGap, KnowledgeGapHit
from app.models.message import Message
from app.models.site import Site
from app.models.visitor import Visitor
from app.models.visitor_block import VisitorBlock
from app.settings import get_settings


def normalized(expression):
    return func.workspace_search_fold(expression)


def search_text(*columns):
    expression = func.coalesce(columns[0], "")
    for column in columns[1:]:
        expression = expression + literal(" ") + func.coalesce(column, "")
    return expression


def matches(expression, terms):
    return and_(*(normalized(expression).contains(term, autoescape=True) for term in terms))


def excerpt(expression, terms):
    positions = [func.nullif(func.strpos(normalized(expression), term), 0) for term in terms]
    first = func.coalesce(func.least(*positions), 1)
    return func.substr(expression, func.greatest(first - 45, 1), 220)


class WorkspaceSearchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def sites(self, terms):
        haystack = search_text(Site.name, Site.key, Site.website_url)
        rows = await self.session.execute(
            select(Site.id, Site.name, Site.key, Site.website_url)
            .where(matches(haystack, terms))
            .order_by(
                case((normalized(Site.name) == " ".join(terms), 0), else_=1), Site.name, Site.id
            )
            .limit(12)
        )
        return rows.mappings().all()

    async def records(self, terms, screen, admin):
        query = " ".join(terms)
        result = []
        # Match all terms across contact details, site, classification, and transcript.
        meta = search_text(
            Visitor.name,
            Visitor.email,
            Visitor.phone,
            Site.name,
            case(
                (Conversation.state == "human", "live"),
                (Conversation.state == "queued", "needs attention"),
                else_=Conversation.state,
            ),
            Conversation.intent,
            Conversation.inquiry_type,
            cast(Conversation.id, String),
        )

        def message_match(term):
            return (
                select(Message.id)
                .where(
                    Message.conversation_id == Conversation.id,
                    normalized(Message.body).contains(term, autoescape=True),
                )
                .exists()
            )

        condition = and_(*(or_(matches(meta, [term]), message_match(term)) for term in terms))
        preview = (
            select(excerpt(Message.body, terms))
            .where(Message.conversation_id == Conversation.id)
            .order_by(
                case((or_(*(matches(Message.body, [term]) for term in terms)), 0), else_=1),
                Message.id.desc(),
            )
            .limit(1)
            .scalar_subquery()
        )
        conversations = (
            select(
                Conversation.id,
                func.coalesce(Visitor.name, Visitor.email, literal("Visitor")).label("title"),
                preview.label("excerpt"),
                Site.name.label("site_name"),
                Conversation.site_id,
                Conversation.state.label("status"),
            )
            .join(Visitor, Visitor.id == Conversation.visitor_id)
            .join(Site, Site.id == Conversation.site_id)
        )
        if screen == "data":
            conversations = conversations.where(Conversation.prechat_submission_id.is_not(None))
        else:
            conversations = conversations.where(Conversation.state != "prechat")
        rows = (
            (
                await self.session.execute(
                    conversations.where(condition)
                    .order_by(
                        case((normalized(Visitor.name) == query, 0), else_=1),
                        Conversation.last_message_at.desc(),
                        Conversation.id,
                    )
                    .limit(12)
                )
            )
            .mappings()
            .all()
        )
        result.extend(
            ("conversation", "data" if screen == "data" else "inbox", row) for row in rows
        )

        specs = [
            (
                "response",
                "canned-responses",
                CannedReply,
                CannedReply.shortcut,
                CannedReply.body,
                search_text(
                    CannedReply.shortcut,
                    func.canned_aliases_as_text(CannedReply.aliases),
                    CannedReply.body,
                ),
                CannedReply.site_id,
                CannedReply.updated_at,
                None,
            ),
            (
                "page",
                "knowledge",
                KbPage,
                KbPage.title,
                KbPage.content_text,
                search_text(KbPage.title, KbPage.url, KbPage.content_text),
                KbPage.site_id,
                KbPage.fetched_at,
                KbPage.source_id,
            ),
            (
                "source",
                "knowledge",
                KbSource,
                func.coalesce(KbSource.display_name, KbSource.start_url),
                KbSource.start_url,
                search_text(KbSource.display_name, KbSource.start_url),
                KbSource.site_id,
                KbSource.updated_at,
                KbSource.id,
            ),
            (
                "gap",
                "suggested-faqs",
                KnowledgeGap,
                KnowledgeGap.question,
                KnowledgeGap.note,
                search_text(KnowledgeGap.question, KnowledgeGap.note),
                KnowledgeGap.site_id,
                KnowledgeGap.created_at,
                KnowledgeGap.status,
            ),
            (
                "block",
                "blocked",
                VisitorBlock,
                func.coalesce(
                    VisitorBlock.email, VisitorBlock.phone, cast(VisitorBlock.ip, String)
                ),
                literal("Blocked visitor"),
                search_text(VisitorBlock.email, VisitorBlock.phone, cast(VisitorBlock.ip, String)),
                VisitorBlock.site_id,
                VisitorBlock.created_at,
                None,
            ),
        ]
        for kind, target, model, title, body, text, site_id, date, extra in specs:
            stmt = select(
                model.id,
                func.left(title, 180).label("title"),
                excerpt(body, terms).label("excerpt"),
                site_id.label("site_id"),
                Site.name.label("site_name"),
                (extra if extra is not None else literal(None)).label("extra"),
            )
            stmt = stmt.outerjoin(Site, Site.id == site_id).where(
                and_(*(or_(matches(text, [term]), matches(Site.name, [term])) for term in terms))
            )
            if kind == "gap":
                settings = get_settings()
                recent = (
                    select(func.count(func.distinct(KnowledgeGapHit.conversation_id)))
                    .where(
                        KnowledgeGapHit.gap_id == KnowledgeGap.id,
                        KnowledgeGapHit.created_at
                        >= datetime.now(UTC) - timedelta(days=settings.knowledge_gap_window_days),
                    )
                    .scalar_subquery()
                )
                spike = (
                    select(func.count(func.distinct(KnowledgeGapHit.conversation_id)))
                    .where(
                        KnowledgeGapHit.gap_id == KnowledgeGap.id,
                        KnowledgeGapHit.created_at
                        >= datetime.now(UTC) - timedelta(hours=settings.knowledge_gap_spike_hours),
                    )
                    .scalar_subquery()
                )
                stmt = stmt.where(
                    or_(
                        KnowledgeGap.status != "open",
                        recent >= settings.knowledge_gap_min_conversations,
                        spike >= settings.knowledge_gap_spike_conversations,
                    )
                )
            rows = (
                (
                    await self.session.execute(
                        stmt.order_by(
                            case(
                                (normalized(title) == query, 0),
                                (normalized(title).startswith(query, autoescape=True), 1),
                                else_=2,
                            ),
                            date.desc(),
                            model.id,
                        ).limit(12)
                    )
                )
                .mappings()
                .all()
            )
            result.extend((kind, target, row) for row in rows)
        chunk_text = search_text(KbChunk.canonical_question, KbChunk.heading, KbChunk.body)
        chunks = select(
            KbChunk.id,
            case(
                (func.jsonb_array_length(KbChunk.origin_urls) >= 2, KbSource.general_tab_id),
                else_=KbChunk.page_id,
            ).label("page_id"),
            KbPage.source_id.label("extra"),
            KbChunk.site_id,
            Site.name.label("site_name"),
            func.coalesce(KbChunk.canonical_question, KbChunk.heading).label("title"),
            excerpt(KbChunk.body, terms).label("excerpt"),
        )
        chunks = (
            chunks.join(KbPage, KbPage.id == KbChunk.page_id)
            .join(KbSource, KbSource.id == KbPage.source_id)
            .join(Site, Site.id == KbChunk.site_id)
            .join(KbSnapshot, KbSnapshot.id == KbChunk.snapshot_id)
        )
        chunks = chunks.where(
            KbSnapshot.state == "live",
            and_(*(or_(matches(chunk_text, [term]), matches(Site.name, [term])) for term in terms)),
        )
        rows = (
            (
                await self.session.execute(
                    chunks.order_by(
                        case((normalized(KbChunk.canonical_question) == query, 0), else_=1),
                        KbChunk.page_id,
                        KbChunk.ordinal,
                    ).limit(12)
                )
            )
            .mappings()
            .all()
        )
        result.extend(("answer", "knowledge", row) for row in rows)
        if admin:
            rows = (
                (
                    await self.session.execute(
                        select(
                            AppLog.id,
                            AppLog.event.label("title"),
                            excerpt(AppLog.message, terms).label("excerpt"),
                            AppLog.level.label("status"),
                        )
                        .where(
                            AppLog.created_at >= datetime.now(UTC) - timedelta(days=7),
                            matches(
                                search_text(
                                    AppLog.event, AppLog.message, AppLog.source, AppLog.level
                                ),
                                terms,
                            ),
                        )
                        .order_by(AppLog.created_at.desc(), AppLog.id)
                        .limit(12)
                    )
                )
                .mappings()
                .all()
            )
            result.extend(("log", "logs", row) for row in rows)
        return result
