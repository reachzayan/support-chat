"""Results and errors shared by conversation commands and reads."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.models.conversation import Conversation
from app.models.message import Message


class CommandError(Exception):
    def __init__(self, code: str, **extra: Any) -> None:
        self.code = code
        self.extra = extra
        super().__init__(code)


@dataclass
class CommandResult:
    conversation: Conversation
    site_key: str
    message: Message | None = None
    event: str = "message"
    client_message_id: str | None = None
    submission_id: str | None = None
    duplicate: bool = False
    generation_id: UUID | None = None


@dataclass(frozen=True)
class ReturningIdentity:
    display_name: str
    email_hint: str
    phone_hint: str | None
    chat_count: int


@dataclass(frozen=True)
class VisitorConversationSummary:
    id: UUID
    state: str
    inquiry_type: str | None
    created_at: datetime
    last_message_at: datetime
    assigned_agent: dict | None
    is_current: bool
    preview: str | None = None


@dataclass
class BootstrapResult:
    site_key: str
    site_name: str
    greeting: str
    privacy_url: str
    contact_info: list[str]
    site_id: UUID
    parent_origin: str
    mode: Literal["conversation", "identity", "history", "forgotten"]
    resume_token: str | None
    bot_enabled: bool
    human_enabled: bool
    visitor_id: UUID | None = None
    conversation_id: UUID | None = None
    conversation_state: str | None = None
    assigned_agent: dict | None = None
    messages: list[Message] | None = None
    visitor_profile: dict[str, str] | None = None
    messages_has_older: bool = False
    identity: ReturningIdentity | None = None
    conversations: list[VisitorConversationSummary] | None = None
    changed_conversations: list[Conversation] = field(default_factory=list)
