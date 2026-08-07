"""add notification delivery guardrails

Revision ID: 5c6d7e8f9a0b
Revises: 4b5c6d7e8f9a
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5c6d7e8f9a0b"
down_revision: Union[str, Sequence[str], None] = "4b5c6d7e8f9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications", sa.Column("dedupe_key", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "notifications", sa.Column("action_url", sa.String(length=1000), nullable=True)
    )
    op.execute("UPDATE notifications SET dedupe_key = event_key, action_url = ''")
    op.alter_column("notifications", "dedupe_key", nullable=False)
    op.alter_column("notifications", "action_url", nullable=False)
    op.create_index(
        "ix_notifications_dedupe",
        "notifications",
        ["user_id", "watchlist_item_id", "notification_type", "created_at"],
    )
    op.create_table(
        "user_notification_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "email_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "timezone", sa.String(length=64), server_default="UTC", nullable=False
        ),
        sa.Column("quiet_hours_start", sa.Time()),
        sa.Column("quiet_hours_end", sa.Time()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(quiet_hours_start IS NULL AND quiet_hours_end IS NULL) OR (quiet_hours_start IS NOT NULL AND quiet_hours_end IS NOT NULL)",
            name="quiet_hours_complete_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "notification_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid()),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32)),
        sa.Column("detail", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["notifications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_audit_user_created",
        "notification_audit_logs",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_audit_user_created", table_name="notification_audit_logs"
    )
    op.drop_table("notification_audit_logs")
    op.drop_table("user_notification_settings")
    op.drop_index("ix_notifications_dedupe", table_name="notifications")
    op.drop_column("notifications", "action_url")
    op.drop_column("notifications", "dedupe_key")
