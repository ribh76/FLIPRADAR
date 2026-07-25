"""refresh token sessions

Revision ID: e6b2c8d9f4a1
Revises: d5a9b7c4e1f0
Create Date: 2026-07-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6b2c8d9f4a1"
down_revision: Union[str, Sequence[str], None] = "d5a9b7c4e1f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "refresh_token_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_jti", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=80), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_token_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_token_sessions")),
    )
    with op.batch_alter_table("refresh_token_sessions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_refresh_token_sessions_expires_at", ["expires_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_refresh_token_sessions_token_hash"),
            ["token_hash"],
            unique=True,
        )
        batch_op.create_index(
            batch_op.f("ix_refresh_token_sessions_token_jti"),
            ["token_jti"],
            unique=True,
        )
        batch_op.create_index(
            "ix_refresh_token_sessions_user_id", ["user_id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("refresh_token_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_refresh_token_sessions_user_id")
        batch_op.drop_index(batch_op.f("ix_refresh_token_sessions_token_jti"))
        batch_op.drop_index(batch_op.f("ix_refresh_token_sessions_token_hash"))
        batch_op.drop_index("ix_refresh_token_sessions_expires_at")
    op.drop_table("refresh_token_sessions")
