"""email MFA challenges and one-time token blacklist

Revision ID: 6a9c3d8e1f2b
Revises: f9a2b3c4d5e6
Create Date: 2026-08-13 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6a9c3d8e1f2b"
down_revision: Union[str, Sequence[str], None] = "f9a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_table(
        "mfa_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_jti", sa.String(length=36), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        sa.UniqueConstraint("token_jti"),
    )
    op.create_index("ix_mfa_challenges_expires_at", "mfa_challenges", ["expires_at"])
    op.create_index("ix_mfa_challenges_token_hash", "mfa_challenges", ["token_hash"])
    op.create_index("ix_mfa_challenges_token_jti", "mfa_challenges", ["token_jti"])
    op.create_table(
        "mfa_token_blacklist",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_jti", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        sa.UniqueConstraint("token_jti"),
    )
    op.create_index(
        "ix_mfa_token_blacklist_created_at", "mfa_token_blacklist", ["created_at"]
    )
    op.create_index(
        "ix_mfa_token_blacklist_token_hash", "mfa_token_blacklist", ["token_hash"]
    )
    op.create_index(
        "ix_mfa_token_blacklist_token_jti", "mfa_token_blacklist", ["token_jti"]
    )


def downgrade() -> None:
    op.drop_index("ix_mfa_token_blacklist_token_jti", table_name="mfa_token_blacklist")
    op.drop_index("ix_mfa_token_blacklist_token_hash", table_name="mfa_token_blacklist")
    op.drop_index("ix_mfa_token_blacklist_created_at", table_name="mfa_token_blacklist")
    op.drop_table("mfa_token_blacklist")
    op.drop_index("ix_mfa_challenges_token_jti", table_name="mfa_challenges")
    op.drop_index("ix_mfa_challenges_token_hash", table_name="mfa_challenges")
    op.drop_index("ix_mfa_challenges_expires_at", table_name="mfa_challenges")
    op.drop_table("mfa_challenges")
    op.drop_column("users", "mfa_enabled")
