import asyncio
import json
import re
from datetime import UTC, datetime
from secrets import token_hex
from urllib.parse import urlsplit
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.connection_manager import connection_manager
from app.http_urls import canonicalize_http_url, canonicalize_https_url
from app.models.article import KbArticle
from app.models.canned_reply import CannedReply
from app.models.conversation import Conversation
from app.models.kb_chunk import KbChunk
from app.models.kb_page import KbPage
from app.models.kb_source import KbSource
from app.models.message import Message
from app.models.site import Site
from app.models.user import User
from app.models.visitor import Visitor
from app.repositories.article_repo import ArticleRepository
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.origins import InvalidOrigin, canonicalize_origins, parent_origin
from app.repositories.site_repo import SiteRepository
from app.services.kb_crawl import fetch_html
from app.settings import AppEnvironment, get_settings

log = structlog.get_logger("site_admin")

KEY_RE = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
NAME_MAX = 120
GREETING_MAX = 300
TITLE_MAX = 300
BODY_MAX = 40_000
ENABLED_TEXT_MAX = 5 * 1024 * 1024
CONTACT_INFO_MAX_ITEMS = 10
CONTACT_INFO_ITEM_MAX = 160


class AdminError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def build_snippet(site_key: str, public_key: str, widget_origin: str) -> str:
    key = json.dumps(site_key).replace("<", "\\u003c")
    pub = json.dumps(public_key).replace("<", "\\u003c")
    return (
        "<script>\n"
        f"  window.__supportchat = {{ siteKey: {key}, publicKey: {pub} }};\n"
        "</script>\n"
        f'<script async src="{widget_origin}/supportchat.js"></script>'
    )


def _plain(value: str, limit: int, empty_ok: bool = False) -> str:
    text = value.strip()
    if not text and not empty_ok:
        raise AdminError("invalid")
    if len(text) > limit:
        raise AdminError("invalid")
    return text


def validate_privacy_url(raw: str, *, production: bool) -> str:
    if production and urlsplit(raw.strip()).scheme.casefold() == "http":
        raise ValueError("privacy URL must use HTTPS in production")
    clean = canonicalize_https_url(raw) if production else canonicalize_http_url(raw)
    if clean is None:
        raise ValueError("privacy URL must use HTTPS in production")
    return clean


def _privacy_url(raw: str) -> str:
    try:
        return validate_privacy_url(
            raw, production=get_settings().app_env is AppEnvironment.PRODUCTION
        )
    except ValueError as exc:
        raise AdminError("invalid") from exc


def _website_url(raw: str) -> str:
    clean = canonicalize_https_url(raw)
    if clean is None:
        raise AdminError("invalid")
    return clean


def _install_hosts(website_url: str) -> set[str]:
    from urllib.parse import urlparse

    host = urlparse(website_url).hostname
    if not host:
        return set()
    folded = host.casefold()
    hosts = {folded}
    if folded.startswith("www."):
        hosts.add(folded.removeprefix("www."))
    else:
        hosts.add(f"www.{folded}")
    return hosts


def _contact_info(raw: list[str] | None) -> list[str]:
    if raw is None:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = (item or "").strip()
        if not text or text in seen:
            continue
        if len(text) > CONTACT_INFO_ITEM_MAX:
            raise AdminError("invalid")
        seen.add(text)
        cleaned.append(text)
        if len(cleaned) > CONTACT_INFO_MAX_ITEMS:
            raise AdminError("too_large")
    return cleaned


def validate_site_origin(raw: str, *, production: bool) -> str:
    origin = canonicalize_origins([raw])[0]
    if production and not origin.startswith("https://"):
        raise ValueError("site origin must use HTTPS in production")
    return origin


def _origins(raw: list[str] | None) -> list[str]:
    if raw is None:
        return []
    try:
        production = get_settings().app_env is AppEnvironment.PRODUCTION
        return [validate_site_origin(item, production=production) for item in raw]
    except (InvalidOrigin, ValueError) as exc:
        raise AdminError("invalid_origin") from exc


def key_from_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().casefold()).strip("-")
    if not slug:
        slug = "site"
    if not slug[0].isalpha():
        slug = f"s-{slug}"
    return slug[:56]


class SiteAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._sites = SiteRepository(session)
        self._articles = ArticleRepository(session)

    async def frame_ancestors_for_site(
        self, site_key: str, public_key: str, raw_parent_origin: str
    ) -> list[str] | None:
        origin = parent_origin(raw_parent_origin)
        if origin is None or origin != raw_parent_origin:
            return None
        site = await self._sites.get_enabled_by_public_identity(site_key, public_key)
        if site is None or origin not in site.allowed_origins:
            return None
        return [origin]

    async def list_sites(self) -> tuple[list[Site], str]:
        settings = get_settings()
        return await self._sites.list_all(), settings.widget_origin

    async def _allocate_key(self, preferred: str) -> str:
        base = preferred[:56]
        candidate = base
        for _ in range(32):
            if KEY_RE.fullmatch(candidate) is not None:
                if await self._sites.get_by_key(candidate) is None:
                    return candidate
            candidate = f"{base[:52]}-{token_hex(2)}"
        raise AdminError("conflict")

    async def create_site(
        self,
        *,
        key: str | None,
        name: str,
        greeting: str,
        privacy_url: str,
        origins: list[str] | None,
        website_url: str | None = None,
        contact_info: list[str] | None = None,
        admin: User | None = None,
    ) -> Site:
        clean_name = _plain(name, NAME_MAX)
        if key is None or not key.strip():
            slug = await self._allocate_key(key_from_name(clean_name))
        else:
            slug = key.strip()
            if KEY_RE.fullmatch(slug) is None:
                raise AdminError("invalid")
            if await self._sites.get_by_key(slug) is not None:
                raise AdminError("conflict")
        clean_website_url = _website_url(website_url) if website_url else None
        clean_contact_info = _contact_info(contact_info)
        site = await self._sites.create(
            key=slug,
            name=clean_name,
            public_key=token_hex(32),
            allowed_origins=_origins(origins),
            greeting=_plain(greeting, GREETING_MAX),
            privacy_url=_privacy_url(privacy_url),
        )
        site.website_url = clean_website_url
        site.contact_info = clean_contact_info
        await self._session.commit()
        if clean_website_url is not None:
            await self._build_kb_from_website(site, admin)
            await self._check_install(site)
        return site

    async def _build_kb_from_website(self, site: Site, admin: User | None) -> None:
        # Best-effort: a slow/unreachable homepage or a queue outage must not
        # fail site creation. The admin can retry from the knowledge screen.
        if admin is None:
            return
        try:
            from app.services.kb_source_admin import KbSourceService

            await KbSourceService(self._session).create_source(
                site.id, admin, mode="prefix", start_url=site.website_url or "", seed_urls=[]
            )
        except Exception:
            log.info("auto_kb_source_failed", site_id=str(site.id))

    async def _check_install(self, site: Site) -> None:
        assert site.website_url is not None
        try:
            html = await asyncio.to_thread(
                fetch_html, site.website_url, _install_hosts(site.website_url)
            )
            installed = site.public_key in html
        except Exception:
            installed = False
        site.widget_installed = installed
        site.widget_checked_at = datetime.now(UTC)
        await self._session.commit()

    async def check_install(self, site_id: UUID) -> Site:
        site = await self._sites.lock_by_id(site_id)
        if site is None:
            raise AdminError("not_found")
        if not site.website_url:
            raise AdminError("no_website_url")
        await self._check_install(site)
        return site

    async def update_site(  # noqa: C901
        self,
        site_id: UUID,
        *,
        name: str | None,
        greeting: str | None,
        privacy_url: str | None,
        origins: list[str] | None,
        website_url: str | None = None,
        contact_info: list[str] | None = None,
        enabled: bool | None = None,
        bot_enabled: bool | None = None,
        human_enabled: bool | None = None,
        callback_window_hours: int | None = None,
    ) -> Site:
        site = await self._sites.lock_by_id(site_id)
        if site is None:
            raise AdminError("not_found")
        if name is not None:
            site.name = _plain(name, NAME_MAX)
        if greeting is not None:
            site.greeting = _plain(greeting, GREETING_MAX)
        if privacy_url is not None:
            site.privacy_url = _privacy_url(privacy_url)
        if origins is not None:
            site.allowed_origins = _origins(origins)
        if contact_info is not None:
            site.contact_info = _contact_info(contact_info)
        if website_url is not None:
            next_website_url = _website_url(website_url) if website_url.strip() else None
            if next_website_url != site.website_url:
                site.widget_installed = None
                site.widget_checked_at = None
            site.website_url = next_website_url
        if enabled is not None:
            site.enabled = enabled
        next_bot = site.bot_enabled if bot_enabled is None else bot_enabled
        next_human = site.human_enabled if human_enabled is None else human_enabled
        if bot_enabled is False and human_enabled is None:
            next_human = False
        if next_human and not next_bot:
            raise AdminError("invalid")
        site.bot_enabled = next_bot
        site.human_enabled = next_human
        if callback_window_hours is not None:
            hours = int(callback_window_hours)
            if hours < 1 or hours > 168:
                raise AdminError("invalid")
            site.callback_window_hours = hours
        closed_rows = []
        if not next_human:
            closed_rows = await ConversationRepository(self._session).close_queued_for_site(site.id)
        await self._session.commit()
        for conversation in closed_rows:
            await connection_manager.after_commit(conversation, site.key, None)
        return site

    async def delete_site(self, site_id: UUID) -> None:
        site = await self._sites.lock_by_id(site_id)
        if site is None:
            raise AdminError("not_found")
        conversation_ids = select(Conversation.id).where(Conversation.site_id == site_id)
        await self._session.execute(
            delete(Message).where(Message.conversation_id.in_(conversation_ids))
        )
        await self._session.execute(delete(Conversation).where(Conversation.site_id == site_id))
        await self._session.execute(delete(Visitor).where(Visitor.site_id == site_id))
        await self._session.execute(delete(KbChunk).where(KbChunk.site_id == site_id))
        await self._session.execute(delete(KbPage).where(KbPage.site_id == site_id))
        await self._session.execute(delete(KbSource).where(KbSource.site_id == site_id))
        await self._session.execute(delete(KbArticle).where(KbArticle.site_id == site_id))
        await self._session.execute(delete(CannedReply).where(CannedReply.site_id == site_id))
        await self._session.execute(delete(Site).where(Site.id == site_id))
        await self._session.commit()

    async def update_off_brand_list(self, site_id: UUID, items: list[str]) -> Site:
        site = await self._sites.lock_by_id(site_id)
        if site is None:
            raise AdminError("not_found")
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in items:
            token = " ".join((raw or "").strip().casefold().split())
            if not token or token in seen:
                continue
            if len(token) > 80:
                raise AdminError("invalid")
            seen.add(token)
            cleaned.append(token)
            if len(cleaned) > 50:
                raise AdminError("too_large")
        site.off_brand_blocklist = cleaned
        await self._session.commit()
        return site

    async def list_articles(self, site_id: UUID) -> list[KbArticle]:
        site = await self._sites.get_by_id(site_id)
        if site is None:
            raise AdminError("not_found")
        return await self._articles.list_for_site(site_id)

    async def create_article(self, site_id: UUID, admin: User, title: str, body: str) -> KbArticle:
        site = await self._sites.lock_by_id(site_id)
        if site is None:
            raise AdminError("not_found")
        clean_title = _plain(title, TITLE_MAX)
        clean_body = _plain(body, BODY_MAX)
        added = len(clean_title.encode()) + len(clean_body.encode())
        if await self._articles.enabled_text_bytes(site_id) + added > ENABLED_TEXT_MAX:
            raise AdminError("too_large")
        article = KbArticle(
            site_id=site_id,
            title=clean_title,
            body=clean_body,
            enabled=True,
            updated_by=admin.id,
        )
        self._session.add(article)
        await self._session.commit()
        return article

    async def update_article(
        self,
        article_id: UUID,
        admin: User,
        *,
        title: str | None = None,
        body: str | None = None,
        enabled: bool | None = None,
    ) -> KbArticle:
        article = await self._articles.get_by_id(article_id)
        if article is None:
            raise AdminError("not_found")
        site = await self._sites.lock_by_id(article.site_id)
        if site is None:
            raise AdminError("not_found")
        next_title = _plain(title, TITLE_MAX) if title is not None else article.title
        next_body = _plain(body, BODY_MAX) if body is not None else article.body
        next_enabled = article.enabled if enabled is None else enabled
        current = 0
        if article.enabled:
            current = len(article.title.encode()) + len(article.body.encode())
        upcoming = 0
        if next_enabled:
            upcoming = len(next_title.encode()) + len(next_body.encode())
        used = await self._articles.enabled_text_bytes(article.site_id)
        if used - current + upcoming > ENABLED_TEXT_MAX:
            raise AdminError("too_large")
        article.title = next_title
        article.body = next_body
        article.enabled = next_enabled
        article.updated_by = admin.id
        await self._session.commit()
        return article
