"""conversations.escalation_reason + expanded message system_reason

Revision ID: 13aescalreason
Revises: 12offbrand01
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "13aescalreason"
down_revision: str | Sequence[str] | None = "12offbrand01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ESCALATION_REASONS = (
    "visitor_request",
    "sensitive",
    "individual_case",
    "retrieval_miss",
    "sufficiency_fail",
    "provider_timeout",
    "repeated_miss",
    "policy_boundary",
    "rate_ceiling",
    "off_topic",
)

_SYSTEM_REASONS = (
    "answer",
    "clarify",
    "escalate",
    "tech_fail",
    "policy_boundary",
    "out_of_scope",
    "insufficient",
    "sensitive",
    *_ESCALATION_REASONS,
)


def upgrade() -> None:
    op.add_column("conversations", sa.Column("escalation_reason", sa.Text(), nullable=True))
    allowed = ", ".join(f"'{item}'" for item in _ESCALATION_REASONS)
    op.create_check_constraint(
        "conversations_escalation_reason_check",
        "conversations",
        f"escalation_reason IS NULL OR escalation_reason IN ({allowed})",
    )
    op.drop_constraint("ck_messages_system_reason", "messages", type_="check")
    system_allowed = ", ".join(f"'{item}'" for item in _SYSTEM_REASONS)
    op.create_check_constraint(
        "ck_messages_system_reason",
        "messages",
        f"system_reason IS NULL OR system_reason IN ({system_allowed})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_messages_system_reason", "messages", type_="check")
    legacy = (
        "answer",
        "clarify",
        "escalate",
        "tech_fail",
        "policy_boundary",
        "out_of_scope",
        "insufficient",
        "sensitive",
    )
    allowed = ", ".join(f"'{item}'" for item in legacy)
    op.create_check_constraint(
        "ck_messages_system_reason",
        "messages",
        f"system_reason IS NULL OR system_reason IN ({allowed})",
    )
    op.drop_constraint("conversations_escalation_reason_check", "conversations", type_="check")
    op.drop_column("conversations", "escalation_reason")
