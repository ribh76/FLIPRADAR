"""refresh token rotation

Revision ID: b8d4e6c9a2f1
Revises: a7c9e1d2f5b4
Create Date: 2026-07-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d4e6c9a2f1"
down_revision: Union[str, Sequence[str], None] = "a7c9e1d2f5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "is_email_verified",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.create_table(
        "refresh_token_blacklist",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_jti", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_token_blacklist_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_token_blacklist")),
    )
    with op.batch_alter_table("refresh_token_blacklist", schema=None) as batch_op:
        batch_op.create_index(
            "ix_refresh_token_blacklist_expires_at", ["expires_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_refresh_token_blacklist_token_hash"),
            ["token_hash"],
            unique=True,
        )
        batch_op.create_index(
            batch_op.f("ix_refresh_token_blacklist_token_jti"),
            ["token_jti"],
            unique=True,
        )
        batch_op.create_index(
            "ix_refresh_token_blacklist_user_id", ["user_id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("refresh_token_blacklist", schema=None) as batch_op:
        batch_op.drop_index("ix_refresh_token_blacklist_user_id")
        batch_op.drop_index(batch_op.f("ix_refresh_token_blacklist_token_jti"))
        batch_op.drop_index(batch_op.f("ix_refresh_token_blacklist_token_hash"))
        batch_op.drop_index("ix_refresh_token_blacklist_expires_at")
    op.drop_table("refresh_token_blacklist")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "is_email_verified")
