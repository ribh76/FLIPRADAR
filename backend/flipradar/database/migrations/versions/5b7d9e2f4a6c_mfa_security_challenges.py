"""MFA security questions and verification throttling."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5b7d9e2f4a6c"
down_revision: Union[str, Sequence[str], None] = "6a9c3d8e1f2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mfa_challenges",
        sa.Column(
            "security_question_id",
            sa.String(length=40),
            nullable=False,
            server_default="first_pet",
        ),
    )
    op.add_column(
        "mfa_challenges",
        sa.Column(
            "failed_attempt_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.create_table(
        "mfa_security_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.String(length=40), nullable=False),
        sa.Column("answer_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "question_id"),
    )
    op.create_index(
        "ix_mfa_security_questions_user_question",
        "mfa_security_questions",
        ["user_id", "question_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mfa_security_questions_user_question", table_name="mfa_security_questions"
    )
    op.drop_table("mfa_security_questions")
    op.drop_column("mfa_challenges", "failed_attempt_count")
    op.drop_column("mfa_challenges", "security_question_id")
