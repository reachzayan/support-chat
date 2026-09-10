from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KbPageLlmExtract(Base):
    __tablename__ = "kb_page_llm_extracts"
    __table_args__ = (
        UniqueConstraint(
            "page_id",
            "content_sha256",
            "prompt_version",
            name="uq_kb_page_llm_extracts_page_hash_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    page_id: Mapped[UUID] = mapped_column(ForeignKey("kb_pages.id", ondelete="CASCADE"))
    content_sha256: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String)
    input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cache_read_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
