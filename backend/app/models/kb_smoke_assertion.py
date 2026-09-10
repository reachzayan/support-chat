from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KbSmokeAssertion(Base):
    __tablename__ = "kb_smoke_assertions"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    source_id: Mapped[UUID] = mapped_column(ForeignKey("kb_sources.id", ondelete="CASCADE"))
    must_include: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    must_exclude: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
