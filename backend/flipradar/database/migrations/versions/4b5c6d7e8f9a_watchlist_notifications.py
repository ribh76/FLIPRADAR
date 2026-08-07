"""add watchlist notification storage

Revision ID: 4b5c6d7e8f9a
Revises: 3a4b5c6d7e8f
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4b5c6d7e8f9a"
down_revision: Union[str, Sequence[str], None] = "3a4b5c6d7e8f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_item_id", sa.Uuid()),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "is_in_app", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "email_eligible",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("email_sent_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "notification_type IN ('price_drop', 'target_reached', 'ended_listing', 'deal_score')",
            name="notification_type_allowed",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["watchlist_item_id"], ["watchlist_items.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key"),
    )
    op.create_index(
        "ix_notifications_user_created", "notifications", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_notifications_email_pending",
        "notifications",
        ["email_eligible", "email_sent_at"],
    )
    op.create_table(
        "price_drop_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("previous_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("drop_percent", sa.Numeric(7, 2), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["notifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "target_reached_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("target_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_price", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["notifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ended_listing_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["notifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "deal_score_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("previous_score", sa.Numeric(5, 2)),
        sa.Column("current_score", sa.Numeric(5, 2), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["notifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column(
            "in_app_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "email_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
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
            "notification_type IN ('price_drop', 'target_reached', 'ended_listing', 'deal_score')",
            name="notification_preference_type_allowed",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "notification_type", name="uq_notification_preference_user_type"
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("deal_score_notifications")
    op.drop_table("ended_listing_notifications")
    op.drop_table("target_reached_notifications")
    op.drop_table("price_drop_notifications")
    op.drop_index("ix_notifications_email_pending", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
