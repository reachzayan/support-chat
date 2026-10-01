from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.message_citation import MessageCitation


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "site_id"],
            ["conversations.id", "conversations.site_id"],
            name="fk_messages_conversation_site",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "site_id"],
            ["kb_snapshots.id", "kb_snapshots.site_id"],
            name="fk_messages_snapshot_site",
            ondelete="SET NULL (snapshot_id)",
        ),
        CheckConstraint("role IN ('visitor','bot','agent','system')", name="ck_messages_role"),
        CheckConstraint(
            "(role IN ('visitor','agent') AND client_message_id IS NOT NULL) OR "
            "(role IN ('bot','system') AND client_message_id IS NULL)",
            name="ck_messages_client_id",
        ),
        CheckConstraint(
            "(role = 'agent' AND author_user_id IS NOT NULL) OR "
            "(role <> 'agent' AND author_user_id IS NULL)",
            name="ck_messages_author",
        ),
        CheckConstraint(
            "(role = 'bot' AND ("
            "(source_article_ids IS NOT NULL AND cardinality(source_article_ids) > 0) OR "
            "(source_chunk_ids IS NOT NULL AND cardinality(source_chunk_ids) > 0) OR "
            "system_reason IN ("
            "'clarify','insufficient','tech_fail','policy_boundary',"
            "'off_topic','out_of_scope','sensitive','uncited_advisory','canned'"
            ")"
            ")) OR "
            "(role <> 'bot' AND source_article_ids IS NULL AND source_chunk_ids IS NULL)",
            name="ck_messages_sources",
        ),
        Index(
            "uq_messages_client_id",
            "conversation_id",
            "client_message_id",
            unique=True,
            postgresql_where=text("client_message_id IS NOT NULL"),
        ),
        Index("ix_messages_conversation_id", "conversation_id", "id"),
        UniqueConstraint("id", "site_id", name="uq_messages_id_site"),
        CheckConstraint(
            "system_reason IS NULL OR system_reason IN ("
            "'answer','clarify','escalate','tech_fail','policy_boundary',"
            "'out_of_scope','insufficient','sensitive',"
            "'visitor_request','individual_case','retrieval_miss',"
            "'sufficiency_fail','provider_timeout','repeated_miss',"
            "'rate_ceiling','off_topic','uncited_advisory','canned')",
            name="ck_messages_system_reason",
        ),
        CheckConstraint(
            "response_outcome IS NULL OR response_outcome IN ("
            "'exact_answer','synthesized_answer','clarification','partial_answer',"
            "'knowledge_gap','boundary')",
            name="ck_messages_response_outcome",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column()
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"))
    client_message_id: Mapped[UUID | None] = mapped_column(nullable=True)
    role: Mapped[str] = mapped_column(String)
    author_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    source_article_ids: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), nullable=True
    )
    source_chunk_ids: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), nullable=True
    )
    snapshot_id: Mapped[UUID | None] = mapped_column(nullable=True)
    system_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    source_urls: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    display_locator: Mapped[str | None] = mapped_column(String, nullable=True)
    source_title: Mapped[str | None] = mapped_column(String, nullable=True)
    response_outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    response_reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    citations: Mapped[list["MessageCitation"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", lazy="selectin"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


@event.listens_for(Message, "before_insert")
def _fill_message_site_id(_mapper, connection, target: "Message") -> None:
    if target.site_id is not None:
        return
    from app.models.conversation import Conversation

    site_id = connection.execute(
        select(Conversation.site_id).where(Conversation.id == target.conversation_id)
    ).scalar_one()
    target.site_id = site_id
