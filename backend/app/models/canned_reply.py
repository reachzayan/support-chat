from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SEARCH_DOCUMENT_SQL = (
    "setweight(to_tsvector('english', coalesce(shortcut, '')), 'A') || "
    "setweight(to_tsvector('english', canned_aliases_as_text(aliases)), 'A') || "
    "setweight(to_tsvector('english', coalesce(body, '')), 'B')"
)


class CannedReply(Base):
    __tablename__ = "canned_replies"
    __table_args__ = (
        Index("ix_canned_replies_search", "search_document", postgresql_using="gin"),
        Index(
            "ix_canned_replies_bot_scope",
            "site_id",
            postgresql_where=text("enabled AND bot_eligible"),
        ),
        Index(
            "uq_canned_replies_general_shortcut_lower",
            text("lower(shortcut)"),
            unique=True,
            postgresql_where=text("site_id IS NULL"),
        ),
        Index(
            "uq_canned_replies_site_shortcut_lower",
            "site_id",
            text("lower(shortcut)"),
            unique=True,
            postgresql_where=text("site_id IS NOT NULL"),
        ),
        Index(
            "uq_canned_replies_external_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        CheckConstraint(
            "suggestion_event IS NULL OR suggestion_event IN "
            "('start_chat','idle','good_rate','bad_rate','transfer')",
            name="ck_canned_replies_suggestion_event",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    site_id: Mapped[UUID | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    shortcut: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default=text("'{}'::character varying[]"),
        default=list,
    )
    external_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    suggestion_event: Mapped[str | None] = mapped_column(String, nullable=True)
    bot_eligible: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False, default=True
    )
    embedder_id: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    search_document: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(SEARCH_DOCUMENT_SQL, persisted=True),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
