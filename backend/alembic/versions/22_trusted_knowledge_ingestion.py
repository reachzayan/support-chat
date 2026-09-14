"""Make administrator-selected website ingestion immediately live.

The review columns from revision 20 remain as compatibility metadata for
existing rows, but they no longer participate in retrieval or publication.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "22trustedknowledge"
down_revision: str | Sequence[str] | None = "21unconditionalgrounded"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_kb_snapshots_state", "kb_snapshots", type_="check")
    op.create_check_constraint(
        "ck_kb_snapshots_state",
        "kb_snapshots",
        "state IN ('building','validated','live','superseded','failed')",
    )
    op.drop_constraint("ck_kb_chunks_approval_review", "kb_chunks", type_="check")
    op.alter_column("kb_chunks", "approved", server_default=sa.text("true"))
    op.alter_column("kb_chunks", "review_status", server_default=sa.text("'approved'"))
    op.execute(
        "UPDATE kb_chunks SET approved = true, review_status = 'approved', "
        "topic_label = coalesce(nullif(btrim(topic_label), ''), nullif(btrim(heading), ''))"
    )
    # If an older database contains several unreviewed candidates, retain only
    # the newest candidate per source before promoting it to live.  This keeps
    # the existing one-live-snapshot invariant intact.
    op.execute(
        "UPDATE kb_snapshots AS current SET state = 'superseded' "
        "WHERE current.state = 'live' AND EXISTS ("
        "SELECT 1 FROM kb_snapshots AS candidate "
        "WHERE candidate.source_id = current.source_id AND candidate.state = 'awaiting_review'"
        ")"
    )
    op.execute(
        "WITH ranked AS ("
        "SELECT id, row_number() OVER (PARTITION BY source_id ORDER BY created_at DESC, id DESC) AS position "
        "FROM kb_snapshots WHERE state = 'awaiting_review'"
        ") UPDATE kb_snapshots SET state = 'superseded' "
        "WHERE id IN (SELECT id FROM ranked WHERE position > 1)"
    )
    op.execute(
        "UPDATE kb_snapshots SET state = 'live', promoted_at = coalesce(promoted_at, now()) "
        "WHERE state = 'awaiting_review'"
    )


def downgrade() -> None:
    op.execute("UPDATE kb_snapshots SET state = 'validated' WHERE state = 'live'")
    op.drop_constraint("ck_kb_snapshots_state", "kb_snapshots", type_="check")
    op.create_check_constraint(
        "ck_kb_snapshots_state",
        "kb_snapshots",
        "state IN ('building','validated','awaiting_review','live','superseded','failed')",
    )
    op.alter_column("kb_chunks", "approved", server_default=sa.text("false"))
    op.alter_column("kb_chunks", "review_status", server_default=sa.text("'legacy_unreviewed'"))
    op.create_check_constraint(
        "ck_kb_chunks_approval_review",
        "kb_chunks",
        "approved = false OR (review_status = 'approved' AND reviewed_by IS NOT NULL "
        "AND reviewed_at IS NOT NULL AND topic_label IS NOT NULL AND btrim(topic_label) <> '')",
    )
