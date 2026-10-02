"""Turn a suggested FAQ into something the assistant can use.

Kept apart from knowledge_gap_service: the canned and knowledge services reach the chat
connection manager, and the chat service must be able to record a miss without importing them.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.canned_reply_service import CannedReplyService
from app.services.kb_source_admin import KbSourceService
from app.services.knowledge_gap_service import KnowledgeGapError, KnowledgeGapService


async def answer_with_canned_reply(
    session: AsyncSession, gap_id: UUID, user: User, *, shortcut: str, body: str
) -> None:
    gaps = KnowledgeGapService(session)
    gap = await gaps.open_gap(gap_id)
    await CannedReplyService(session).create(
        site_id=gap.site_id,
        shortcut=shortcut,
        body=body,
        bot_eligible=True,
        is_admin=user.is_admin,
    )
    await gaps.close(gap, "canned", user)


async def answer_with_knowledge_text(
    session: AsyncSession, gap_id: UUID, user: User, *, title: str, body: str
) -> None:
    if not user.is_admin:
        raise KnowledgeGapError("forbidden")
    gaps = KnowledgeGapService(session)
    gap = await gaps.open_gap(gap_id)
    await KbSourceService(session).create_text_source(gap.site_id, user, title=title, body=body)
    await gaps.close(gap, "knowledge", user)
