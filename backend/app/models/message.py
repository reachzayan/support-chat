from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
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
            "(source_chunk_ids IS NOT NULL AND cardinality(source_chunk_ids) > 0)"
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
        CheckConstraint(
            "system_reason IS NULL OR system_reason IN ("
            "'answer','clarify','escalate','tech_fail','policy_boundary',"
            "'out_of_scope','insufficient','sensitive',"
            "'visitor_request','individual_case','retrieval_miss',"
            "'sufficiency_fail','provider_timeout','repeated_miss',"
            "'rate_ceiling','off_topic')",
            name="ck_messages_system_reason",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
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
    snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("kb_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    system_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    source_urls: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    display_locator: Mapped[str | None] = mapped_column(String, nullable=True)
    source_title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
