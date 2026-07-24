"""account security checks

Revision ID: a7c9e1d2f5b4
Revises: 4d8f2c1a7b93
Create Date: 2026-07-24 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c9e1d2f5b4"
down_revision: Union[str, Sequence[str], None] = "4d8f2c1a7b93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USER_CHECKS = (
    ("username_canonical", "username = lower(trim(username))"),
    ("email_canonical", "email = lower(trim(email))"),
    (
        "email_supported_domain",
        "(email LIKE '%@%.com' OR email LIKE '%@%.org')",
    ),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE users SET username = lower(trim(username)), email = lower(trim(email))"
    )

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users", schema=None, recreate="always") as batch_op:
            for name, condition in USER_CHECKS:
                batch_op.create_check_constraint(
                    batch_op.f(f"ck_users_{name}"), condition
                )
        return

    for name, condition in USER_CHECKS:
        op.create_check_constraint(op.f(f"ck_users_{name}"), "users", condition)


def downgrade() -> None:
    """Downgrade schema."""
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users", schema=None, recreate="always") as batch_op:
            for name, _condition in reversed(USER_CHECKS):
                batch_op.drop_constraint(batch_op.f(f"ck_users_{name}"), type_="check")
        return

    for name, _condition in reversed(USER_CHECKS):
        op.drop_constraint(op.f(f"ck_users_{name}"), "users", type_="check")
