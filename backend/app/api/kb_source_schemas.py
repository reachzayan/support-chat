from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["website", "text"] = "website"
    mode: str | None = None
    start_url: str | None = None
    seed_urls: list[str] = Field(default_factory=list)
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=40_000)

    @model_validator(mode="after")
    def validate_source_shape(self) -> "SourceIn":
        if self.kind == "website":
            if (
                self.mode is None
                or self.start_url is None
                or self.title is not None
                or self.body is not None
            ):
                raise ValueError("A website source requires mode and start_url")
        elif self.kind == "text":
            if (
                not (self.title or "").strip()
                or not (self.body or "").strip()
                or self.mode is not None
                or self.start_url is not None
                or self.seed_urls
            ):
                raise ValueError("A text source requires title and body")
        return self


class SourcePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=40_000)


class PagePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class ChunkPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class SourceOut(BaseModel):
    id: UUID
    site_id: UUID
    start_url: str
    mode: str
    source_kind: str
    display_name: str | None = None
    status: str
    stage: str = "idle"
    error_code: str | None
    page_count: int
    pages_discovered: int = 0
    pages_fetched: int = 0
    pages_extracted: int = 0
    pages_embedded: int = 0
    pages_failed: int = 0
    pages_skipped_unchanged: int = 0
    last_run_started_at: str | None = None
    last_run_finished_at: str | None = None
    enabled: bool
    snapshot_state: str | None = None
    snapshot_error_code: str | None = None
    validation_errors: list[str] = Field(default_factory=list)


class SourceListOut(BaseModel):
    items: list[SourceOut]


class SnapshotOut(BaseModel):
    id: UUID
    state: str
    created_at: str | None
    promoted_at: str | None
    token_estimate: int
    validation_errors: list[str]
    error_code: str | None


class SnapshotListOut(BaseModel):
    items: list[SnapshotOut]


class EvidenceUnitOut(BaseModel):
    kind: str
    canonical_question: str | None
    heading: str
    answer_verbatim: str
    display_locator: str | None


class DiffChangeOut(BaseModel):
    before: EvidenceUnitOut
    after: EvidenceUnitOut


class DiffOut(BaseModel):
    added: list[EvidenceUnitOut]
    changed: list[DiffChangeOut]
    removed: list[EvidenceUnitOut]


class PageOut(BaseModel):
    id: UUID
    source_id: UUID
    url: str
    title: str
    enabled: bool
    chunk_count: int
    processing_status: str = "pending"
    failure_reason: str | None = None
    last_success_at: str | None = None
    tab: str = "page"


class ChunkOut(BaseModel):
    id: UUID
    ordinal: int
    kind: str
    heading: str
    body: str
    enabled: bool
    origin_urls: list[str] = Field(default_factory=list)


class PageDetailOut(PageOut):
    skip_reason: str | None
    content_text: str
    chunks: list[ChunkOut]


class ProgressEventOut(BaseModel):
    timestamp: str | None
    stage: str
    state: str
    page_url: str
    duration_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    message: str
    renderer: str | None = None
    http_status: int | None = None


class ProgressJobOut(BaseModel):
    page_url: str
    stage: str
    attempt: int
    started_at: str | None
    renderer: str | None = None
    message: str


class ProgressOut(BaseModel):
    source: SourceOut
    recent_events: list[ProgressEventOut]
    current_jobs: list[ProgressJobOut]


class PageListOut(BaseModel):
    items: list[PageOut]
