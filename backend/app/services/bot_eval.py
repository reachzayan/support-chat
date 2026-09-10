"""SampleSite bot evals: independent case spec + observed-reply scoring."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.site import Site
from app.models.visitor import Visitor
from app.repositories.message_repo import MessageRepository
from app.services.conversation_service import ConversationService

DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "evals" / "dataset" / "samplesite.json"
)


@dataclass(frozen=True)
class EvalCase:
    id: str
    family: str
    turns: tuple[str, ...]
    expected_state: str
    expected_reason: str | None = None
    expected_copy: str | None = None
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservedReply:
    state: str
    role: str
    body: str
    system_reason: str | None = None
    source_title: str | None = None


@dataclass(frozen=True)
class EvalVerdict:
    case_id: str
    passed: bool
    failures: tuple[str, ...]


def score_case(case: EvalCase, observed: ObservedReply) -> EvalVerdict:
    failures: list[str] = []
    if observed.state != case.expected_state:
        failures.append(f"state: expected {case.expected_state}, got {observed.state}")
    if case.expected_reason is not None and observed.system_reason != case.expected_reason:
        failures.append(f"reason: expected {case.expected_reason}, got {observed.system_reason}")
    if case.expected_copy is not None and observed.body != case.expected_copy:
        failures.append("copy: expected canned visitor line")
    lowered = (observed.body or "").casefold()
    for needle in case.must_contain:
        if needle.casefold() not in lowered:
            failures.append(f"must_contain: {needle}")
    for needle in case.must_not_contain:
        if needle.casefold() in lowered:
            failures.append(f"must_not_contain: {needle}")
    return EvalVerdict(case_id=case.id, passed=not failures, failures=tuple(failures))


def case_from_dict(raw: dict) -> EvalCase:
    return EvalCase(
        id=str(raw["id"]),
        family=str(raw["family"]),
        turns=tuple(str(item) for item in raw["turns"]),
        expected_state=str(raw["expected_state"]),
        expected_reason=raw.get("expected_reason"),
        expected_copy=raw.get("expected_copy"),
        must_contain=tuple(raw.get("must_contain") or ()),
        must_not_contain=tuple(raw.get("must_not_contain") or ()),
    )


def load_dataset(path: Path | None = None) -> tuple[str, tuple[EvalCase, ...]]:
    payload = json.loads((path or DATASET_PATH).read_text())
    cases = tuple(case_from_dict(item) for item in payload["cases"])
    return str(payload["site_key"]), cases


async def open_eval_conversation(session: AsyncSession, site: Site) -> tuple[Visitor, Conversation]:
    visitor = Visitor(
        site_id=site.id,
        resume_token_hash=uuid4().hex,
        name="Eval Visitor",
        email="eval@supportchat.local",
    )
    session.add(visitor)
    await session.flush()
    conversation = Conversation(site_id=site.id, visitor_id=visitor.id, state="bot")
    session.add(conversation)
    await session.flush()
    return visitor, conversation


def _visible_reply(messages: list[Message]) -> ObservedReply | None:
    for row in reversed(messages):
        if row.role in {"bot", "system"}:
            return ObservedReply(
                state="",
                role=row.role,
                body=row.body,
                system_reason=row.system_reason,
                source_title=row.source_title,
            )
    return None


async def run_case(
    session: AsyncSession,
    site: Site,
    case: EvalCase,
    *,
    parent_origin: str,
    responder=None,
    embedder=None,
) -> tuple[ObservedReply, EvalVerdict]:
    visitor, conversation = await open_eval_conversation(session, site)
    await session.commit()
    service = ConversationService(session, responder=responder, embedder=embedder)
    for body in case.turns:
        result = await service.visitor_message(
            conversation.id, visitor.id, parent_origin, uuid4(), body
        )
        if result.generation_id is not None:
            await service.run_bot_turn(conversation.id, result.generation_id)
    await session.refresh(conversation)
    rows = await MessageRepository(session).list_recent_roles(
        conversation.id, {"bot", "system", "visitor"}, 20
    )
    visible = _visible_reply(list(rows))
    if visible is None:
        observed = ObservedReply(state=conversation.state, role="", body="")
    else:
        observed = ObservedReply(
            state=conversation.state,
            role=visible.role,
            body=visible.body,
            system_reason=visible.system_reason,
            source_title=visible.source_title,
        )
    return observed, score_case(case, observed)
