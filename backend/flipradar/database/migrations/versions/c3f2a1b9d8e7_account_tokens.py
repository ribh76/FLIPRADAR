"""account tokens

Revision ID: c3f2a1b9d8e7
Revises: b8d4e6c9a2f1
Create Date: 2026-07-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f2a1b9d8e7"
down_revision: Union[str, Sequence[str], None] = "b8d4e6c9a2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "account_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_jti", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=80), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_count", sa.Integer(), nullable=False),
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
            name=op.f("fk_account_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_tokens")),
    )
    with op.batch_alter_table("account_tokens", schema=None) as batch_op:
        batch_op.create_index("ix_account_tokens_expires_at", ["expires_at"])
        batch_op.create_index(
            batch_op.f("ix_account_tokens_token_hash"), ["token_hash"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_account_tokens_token_jti"), ["token_jti"], unique=True
        )
        batch_op.create_index(
            "ix_account_tokens_user_purpose_created",
            ["user_id", "purpose", "created_at"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("account_tokens", schema=None) as batch_op:
        batch_op.drop_index("ix_account_tokens_user_purpose_created")
        batch_op.drop_index(batch_op.f("ix_account_tokens_token_jti"))
        batch_op.drop_index(batch_op.f("ix_account_tokens_token_hash"))
        batch_op.drop_index("ix_account_tokens_expires_at")
    op.drop_table("account_tokens")
