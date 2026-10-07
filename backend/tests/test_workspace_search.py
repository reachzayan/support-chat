"""Search contract derived from workspace navigation and real stored records."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db import session_maker
from app.models.app_log import AppLog
from app.models.canned_reply import CannedReply
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.visitor import Visitor
from tests.ws_helpers import (
    ALEX_EMAIL,
    ALEX_NAME,
    ALEX_PASSWORD,
    insert_site,
    insert_staff,
    login_staff,
)


def auth(client, admin=False):
    user = insert_staff(ALEX_EMAIL, ALEX_NAME, ALEX_PASSWORD, is_admin=admin)
    token = login_staff(client, ALEX_EMAIL, ALEX_PASSWORD)
    return user, {"Authorization": f"Bearer {token}"}


async def seed(site):
    async with session_maker()() as session:
        visitor = Visitor(
            site_id=site, resume_token_hash=uuid4().hex, name="Zoë Archer", email="zoe@example.com"
        )
        session.add(visitor)
        await session.flush()
        chat = Conversation(
            site_id=site,
            visitor_id=visitor.id,
            state="closed",
            prechat_submission_id=uuid4(),
            prechat_payload_hash="a" * 64,
        )
        session.add(chat)
        await session.flush()
        session.add(
            Message(
                conversation_id=chat.id,
                site_id=site,
                role="visitor",
                body="A literal 100%_match and payroll question",
                client_message_id=uuid4(),
            )
        )
        reply = CannedReply(shortcut="payroll", body="Payroll turnaround is two days")
        session.add(reply)
        session.add(
            AppLog(
                level="error", source="backend", event="payroll_failure", message="Payroll failed"
            )
        )
        session.add(
            AppLog(
                level="error",
                source="backend",
                event="expired_only",
                message="expired_only",
                created_at=datetime.now(UTC) - timedelta(days=9),
            )
        )
        await session.commit()
        return str(chat.id), str(reply.id)


def search(client, headers, query, screen="inbox"):
    response = client.post("/api/search", headers=headers, json={"query": query, "screen": screen})
    assert response.status_code == 200, response.text
    return response.json()


def test_requires_staff_and_validates_input(client):
    assert client.post("/api/search", json={"query": "test", "screen": "inbox"}).status_code == 401
    _, headers = auth(client)
    assert (
        client.post(
            "/api/search", headers=headers, json={"query": "x" * 201, "screen": "inbox"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/search", headers=headers, json={"query": "test", "screen": "secrets"}
        ).status_code
        == 422
    )


def test_current_screen_first_and_exact_deep_links(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "public-key")
    chat, reply = client.portal.call(seed, site)
    result = search(client, headers, "payroll")
    assert [x["id"] for x in result["current"]] == [f"conversation:{chat}"]
    assert result["current"][0]["href"] == f"/admin/inbox?conversation={chat}"
    canned = next(x for x in result["other"] if x["id"] == f"response:{reply}")
    assert canned["href"] == f"/admin/canned-responses?scope=general&response={reply}"
    assert not any(x["screen"] == "logs" for x in result["other"])
    assert not any("public-key" in str(x) for x in result.values())


def test_site_settings_intent_and_site_specific_notifications(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "public-key")
    insert_site("other", "Other site", "other-key")
    result = search(client, headers, "SampleSite site settings")
    assert result["navigation"][0]["href"] == f"/admin/sites?site={site}"
    assert result["navigation"][0]["title"] == "SampleSite · Site settings"
    result = search(client, headers, "samplesite notifications")
    assert result["navigation"][0]["href"] == f"/admin/notifications?site={site}"


def test_case_accents_multi_field_partial_and_literal_wildcards(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "public-key")
    chat, _ = client.portal.call(seed, site)
    for query in [" ZOE  ARCH ", "zoe SampleSite", "100%_match"]:
        assert search(client, headers, query)["current"][0]["id"] == f"conversation:{chat}"
    assert search(client, headers, "100%_missing")["current"] == []


def test_admin_logs_retention_and_short_queries(client):
    _, headers = auth(client, admin=True)
    site = insert_site("easy", "SampleSite", "public-key")
    client.portal.call(seed, site)
    assert search(client, headers, "payroll", "logs")["current"][0]["screen"] == "logs"
    assert search(client, headers, "expired_only", "logs")["current"] == []
    assert search(client, headers, " ")["current"] == []


def test_submission_result_fetches_exact_row_and_validates_missing(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "public-key")
    chat, _ = client.portal.call(seed, site)
    result = search(client, headers, "zoe", "data")
    assert result["current"][0]["href"] == f"/admin/data?conversation={chat}"
    detail = client.get(f"/api/conversations/submissions/{chat}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["visitor"]["email"] == "zoe@example.com"
    assert (
        client.get(f"/api/conversations/submissions/{uuid4()}", headers=headers).status_code == 404
    )


def test_log_destination_is_exact_admin_only_and_retention_limited(client):
    _, headers = auth(client, admin=True)
    site = insert_site("easy", "SampleSite", "public-key")
    client.portal.call(seed, site)
    result = search(client, headers, "payroll", "logs")["current"][0]
    log = result["href"].split("log=")[1]
    assert client.get(f"/api/logs/{log}", headers=headers).json()["event"] == "payroll_failure"
    assert client.get(f"/api/logs/{uuid4()}", headers=headers).status_code == 404


def test_shortcut_exact_ranking_and_hidden_content_do_not_leak(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "public-key")
    _, reply = client.portal.call(seed, site)
    result = search(client, headers, "#payroll", "canned-responses")
    assert result["current"][0]["id"] == f"response:{reply}"


def test_all_content_kinds_have_resolvable_destinations(client):
    user, headers = auth(client, admin=True)
    site = insert_site("easy", "SampleSite", "public-key")

    async def content():
        from app.models.kb_page import KbPage
        from app.models.kb_source import KbSource
        from app.models.knowledge_gap import KnowledgeGap
        from app.models.visitor_block import VisitorBlock

        async with session_maker()() as session:
            source = KbSource(
                site_id=site,
                start_url="https://easy.example/handbook",
                display_name="Payroll handbook",
                mode="list",
            )
            session.add(source)
            await session.flush()
            page = KbPage(
                site_id=site,
                source_id=source.id,
                title="Payroll deadline",
                url="https://easy.example/deadline",
                content_text="Payroll closes Friday",
                content_sha256="abc",
                http_status=200,
            )
            gap = KnowledgeGap(
                site_id=site, question="How do payroll checks work?", status="dismissed"
            )
            block = VisitorBlock(site_id=site, email="payroll@example.com", created_by=user)
            session.add_all([page, gap, block])
            await session.commit()
            return str(source.id), str(page.id), str(gap.id), str(block.id)

    source, page, gap, block = client.portal.call(content)
    knowledge = search(client, headers, "payroll", "knowledge")["current"]
    assert {i["kind"] for i in knowledge} == {"page", "source"}
    assert (
        next(i for i in knowledge if i["kind"] == "page")["href"]
        == f"/admin/knowledge?site={site}&source={source}&page={page}"
    )
    assert (
        search(client, headers, "payroll", "blocked")["current"][0]["href"]
        == f"/admin/blocked?block={block}"
    )
    assert (
        search(client, headers, "payroll", "suggested-faqs")["current"][0]["href"]
        == f"/admin/suggested-faqs?site={site}&view=dismissed&gap={gap}"
    )


def test_result_count_is_bounded_and_exact_shortcut_precedes_body(client):
    _, headers = auth(client)

    async def replies():
        async with session_maker()() as session:
            for n in range(35):
                session.add(CannedReply(shortcut=f"different_{n}", body="Payroll information"))
            exact = CannedReply(shortcut="payroll", body="Useful answer")
            session.add(exact)
            await session.commit()
            return str(exact.id)

    exact = client.portal.call(replies)
    result = search(client, headers, "payroll", "canned-responses")
    assert len(result["current"]) == 12
    assert result["current"][0]["id"] == f"response:{exact}"
    assert len({r["id"] for r in result["current"]}) == 12


def test_indexed_fold_handles_compatibility_characters_and_accents(client):
    _, headers = auth(client)
    insert_site("resume", "Résumé ﬃrm", "public-key")
    assert search(client, headers, "resume ffi", "sites")["current"][0]["title"] == "Résumé ﬃrm"

    async def plan():
        from sqlalchemy import text

        async with session_maker()() as session:
            await session.execute(text("SET LOCAL enable_seqscan = off"))
            result = await session.execute(
                text(
                    "EXPLAIN SELECT id FROM messages WHERE workspace_search_fold(body) LIKE '%payroll%'"
                )
            )
            return " ".join(row[0] for row in result)

    assert "ix_messages_workspace_search" in client.portal.call(plan)


def test_prechat_drafts_do_not_appear_as_inbox_chats(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "public-key")

    async def draft():
        async with session_maker()() as session:
            visitor = Visitor(site_id=site, resume_token_hash=uuid4().hex, name="Unsubmitted")
            session.add(visitor)
            await session.flush()
            session.add(Conversation(site_id=site, visitor_id=visitor.id, state="prechat"))
            await session.commit()

    client.portal.call(draft)
    assert search(client, headers, "Unsubmitted")["current"] == []
    assert search(client, headers, "Unsubmitted", "data")["current"] == []


def test_preview_shows_the_matching_passage_not_an_unrelated_latest_message(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "public-key")
    chat, _ = client.portal.call(seed, site)

    async def messages():
        async with session_maker()() as session:
            session.add(
                Message(
                    conversation_id=chat,
                    site_id=site,
                    role="visitor",
                    client_message_id=uuid4(),
                    body="An introduction. " * 100 + "Unique reimbursement deadline is Friday.",
                )
            )
            await session.flush()
            session.add(
                Message(
                    conversation_id=chat, site_id=site, role="system", body="Thank you. Chat ended."
                )
            )
            await session.commit()

    client.portal.call(messages)
    result = search(client, headers, "reimbursement")
    assert "reimbursement deadline is Friday" in result["current"][0]["description"]
    assert len(result["current"][0]["description"]) <= 260


def test_shared_knowledge_answer_opens_general_tab_and_excludes_old_snapshots(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "public-key")

    async def answers():
        from app.models.kb_chunk import KbChunk
        from app.models.kb_page import KbPage
        from app.models.kb_snapshot import KbSnapshot
        from app.models.kb_source import KbSource

        async with session_maker()() as session:
            source = KbSource(
                site_id=site, start_url="https://easy.example/", display_name="Handbook"
            )
            session.add(source)
            await session.flush()
            pages = [
                KbPage(
                    site_id=site,
                    source_id=source.id,
                    url=f"https://easy.example/{n}",
                    title=f"Page {n}",
                    content_text="Page introduction",
                    content_sha256=str(n),
                    http_status=200,
                )
                for n in range(2)
            ]
            live = KbSnapshot(site_id=site, source_id=source.id, state="live")
            old = KbSnapshot(site_id=site, source_id=source.id, state="superseded")
            session.add_all([*pages, live, old])
            await session.flush()
            chunk = KbChunk(
                site_id=site,
                page_id=pages[0].id,
                snapshot_id=live.id,
                ordinal=0,
                heading="Leave",
                canonical_question="Shared medical leave policy",
                answer_verbatim="Ask HR",
                body="Shared medical leave: ask HR",
                origin_urls=[p.url for p in pages],
            )
            outdated = KbChunk(
                site_id=site,
                page_id=pages[0].id,
                snapshot_id=old.id,
                ordinal=0,
                heading="Leave",
                canonical_question="Shared medical leave old policy",
                answer_verbatim="Old",
                body="Old shared medical leave",
                origin_urls=[],
            )
            session.add_all([chunk, outdated])
            await session.commit()
            return str(source.id), str(source.general_tab_id), str(chunk.id)

    source, general, chunk = client.portal.call(answers)
    current = search(client, headers, "shared medical", "knowledge")["current"]
    assert len(current) == 1
    assert (
        current[0]["href"]
        == f"/admin/knowledge?site={site}&source={source}&page={general}&chunk={chunk}"
    )
    detail = client.get(f"/api/kb-pages/{general}", headers=headers)
    assert detail.status_code == 200
    assert [c["id"] for c in detail.json()["chunks"]] == [chunk]
    pages = client.get(f"/api/kb-sources/{source}/pages", headers=headers).json()["items"]
    assert general in [p["id"] for p in pages]


def test_unqualified_open_faqs_do_not_appear_in_search(client):
    _, headers = auth(client)
    site = insert_site("easy", "SampleSite", "public-key")

    async def gap():
        from app.models.knowledge_gap import KnowledgeGap

        async with session_maker()() as session:
            session.add(KnowledgeGap(site_id=site, question="Not repeated enough", status="open"))
            await session.commit()

    client.portal.call(gap)
    assert search(client, headers, "Not repeated", "suggested-faqs")["current"] == []
