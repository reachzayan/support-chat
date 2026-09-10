from dataclasses import dataclass, field
from uuid import UUID

import structlog
from anthropic import AsyncAnthropic

from app.llm.prompts import document_body, document_title, system_rules_for, visitor_turn_text
from app.llm.safety_markers import contains_injection_marker
from app.models.site import Site
from app.services import output_validator
from app.services.pii_redactor import redact_for_model
from app.settings import get_settings

log = structlog.get_logger("bot")


@dataclass
class BufferedAnswer:
    body: str
    source_chunk_ids: list[UUID]
    accepted: bool
    unsafe: bool = False
    source_article_ids: list[UUID] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    snapshot_id: UUID | None = None
    display_locator: str | None = None
    source_title: str | None = None
    reject_reason: str | None = None

    def __post_init__(self) -> None:
        if self.source_article_ids and not self.source_chunk_ids:
            self.source_chunk_ids = list(self.source_article_ids)
        elif self.source_chunk_ids and not self.source_article_ids:
            self.source_article_ids = list(self.source_chunk_ids)


def extract_text_and_citations(blocks: list, hits: list) -> tuple[str, list[UUID]]:
    texts: list[str] = []
    cited_ids: list[UUID] = []
    for block in blocks:
        if getattr(block, "type", None) == "text" and hasattr(block, "text"):
            texts.append(block.text)
        for citation in getattr(block, "citations", None) or []:
            index = getattr(citation, "document_index", None)
            if isinstance(index, int) and 0 <= index < len(hits):
                chunk_id = hits[index].id
                if chunk_id not in cited_ids:
                    cited_ids.append(chunk_id)
    return "".join(texts).strip(), cited_ids


def join_sdk_completion(blocks: list, hits: list) -> str:
    """Compatibility shim for callers that still expect a single string."""
    body, cited = extract_text_and_citations(blocks, hits)
    if cited:
        return body
    return body


def output_is_safe(
    body: str,
    allowed_ids: list[UUID],
    cited: list[UUID],
    *,
    live_urls: set[str] | None = None,
    citation_urls: list[str] | None = None,
    cited_answer_text: str = "",
    off_brand_blocklist: list[str] | None = None,
    curated_refusal: bool = False,
) -> bool:
    outcome = output_validator.evaluate(
        body,
        allowed_ids=allowed_ids,
        cited=cited,
        live_urls=live_urls,
        citation_urls=citation_urls,
        cited_answer_text=cited_answer_text,
        off_brand_blocklist=off_brand_blocklist,
        curated_refusal=curated_refusal,
    )
    return outcome.accepted


def _document_block(item: object, *, cache_control: bool = False) -> dict:
    block: dict = {
        "type": "document",
        "source": {
            "type": "text",
            "media_type": "text/plain",
            "data": redact_for_model(document_body(item)),
        },
        "title": redact_for_model(document_title(item)),
        "citations": {"enabled": True},
    }
    if cache_control:
        block["cache_control"] = {"type": "ephemeral"}
    return block


def _scan_documents_for_injection(documents: list) -> None:
    for item in documents:
        body = document_body(item)
        if contains_injection_marker(body):
            log.info(
                "role_swap_detected",
                chunk_id=str(getattr(item, "id", "")),
            )


class BotResponder:
    def __init__(self, complete=None) -> None:
        self._complete = complete

    async def generate(self, site: Site, visitor_text: str, hits: list) -> BufferedAnswer:
        if not hits:
            return BufferedAnswer("", [], False)
        if self._complete is not None:
            try:
                raw = await self._complete(visitor_turn_text(site.name, visitor_text))
            except Exception as exc:
                log.info("provider_error", error_class=type(exc).__name__)
                return BufferedAnswer("", [], False)
            if isinstance(raw, BufferedAnswer):
                return raw
            body = raw.strip() if isinstance(raw, str) else ""
            return BufferedAnswer(body=body, source_chunk_ids=[], accepted=False)
        return await self.generate_from_documents(
            site=site,
            visitor_text=visitor_text,
            documents=hits,
            prior_messages=[],
        )

    async def generate_from_documents(
        self,
        *,
        site: Site,
        visitor_text: str,
        documents: list,
        prior_messages: list[dict],
        live_urls: set[str] | None = None,
        curated_refusal: bool = False,
    ) -> BufferedAnswer:
        allowed = [item.id for item in documents]
        if not documents:
            return BufferedAnswer("", [], False)
        _scan_documents_for_injection(documents)
        try:
            body, cited = await self._complete_documents(
                site_name=site.name,
                visitor_text=visitor_text,
                documents=documents,
                prior_messages=prior_messages,
            )
        except Exception as exc:
            log.info("provider_error", error_class=type(exc).__name__)
            return BufferedAnswer("", [], False)
        by_id = {item.id: item for item in documents}
        urls: list[str] = []
        locator = None
        title = None
        snapshot_id = None
        cited_text_parts: list[str] = []
        for chunk_id in cited:
            item = by_id.get(chunk_id)
            if item is None:
                continue
            url = getattr(item, "url", None)
            if isinstance(url, str) and url and url not in urls:
                urls.append(url)
            if locator is None:
                locator = getattr(item, "display_locator", None)
            if title is None:
                title = document_title(item)
            if snapshot_id is None:
                snapshot_id = getattr(item, "snapshot_id", None)
            cited_text_parts.append(document_body(item))
        blocklist = list(getattr(site, "off_brand_blocklist", None) or [])
        outcome = output_validator.evaluate(
            body,
            allowed_ids=allowed,
            cited=cited,
            live_urls=live_urls,
            citation_urls=urls,
            cited_answer_text="\n".join(cited_text_parts),
            off_brand_blocklist=blocklist,
            curated_refusal=curated_refusal,
        )
        accepted = outcome.accepted
        leak = outcome.reason in {
            "injection_leak",
            "pii_leak",
            "html_leak",
            "brand_leak",
        }
        return BufferedAnswer(
            body=body,
            source_chunk_ids=cited if accepted else [],
            accepted=accepted,
            unsafe=leak,
            source_urls=urls if accepted else [],
            snapshot_id=snapshot_id if accepted else None,
            display_locator=locator if accepted else None,
            source_title=title if accepted else None,
            reject_reason=None if accepted else outcome.reason,
        )

    async def _complete_documents(
        self,
        *,
        site_name: str,
        visitor_text: str,
        documents: list,
        prior_messages: list[dict],
    ) -> tuple[str, list[UUID]]:
        settings = get_settings()
        client_kwargs: dict = {
            "timeout": settings.anthropic_timeout,
            "max_retries": 1,
        }
        if settings.anthropic_api_key:
            client_kwargs["api_key"] = settings.anthropic_api_key
        client = AsyncAnthropic(**client_kwargs)
        content: list[dict] = []
        last_index = len(documents) - 1
        for index, item in enumerate(documents):
            content.append(_document_block(item, cache_control=index == last_index))
        messages: list[dict] = []
        for item in prior_messages:
            role = item.get("role")
            text = item.get("content")
            if role not in {"user", "assistant"}:
                continue
            if not isinstance(text, str) or not text.strip():
                continue
            if not messages and role == "assistant":
                continue
            messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": content})
        messages.append(
            {
                "role": "user",
                "content": visitor_turn_text(site_name, redact_for_model(visitor_text)),
            }
        )
        system = [
            {
                "type": "text",
                "text": system_rules_for(site_name),
                "cache_control": {"type": "ephemeral"},
            }
        ]
        try:
            response = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=settings.anthropic_max_tokens,
                system=system,
                messages=messages,
            )
        except Exception as exc:
            log.info("provider_error", error_class=type(exc).__name__)
            return "", []
        finally:
            await client.close()
        return extract_text_and_citations(list(response.content), documents)
