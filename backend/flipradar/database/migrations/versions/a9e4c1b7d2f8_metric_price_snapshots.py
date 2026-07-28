"""store price snapshots as condition-specific metric rows

Revision ID: a9e4c1b7d2f8
Revises: d1e2f3a4b5c6
Create Date: 2026-07-28 00:00:00.000000
"""

from datetime import datetime
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "a9e4c1b7d2f8"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_METRICS = {
    "low": "low_price",
    "median": "median_price",
    "average": "average_price",
    "high": "high_price",
    "fair_market_value": "fair_market_value",
}


def _create_new_table() -> None:
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lego_set_id", sa.Uuid(), nullable=False),
        sa.Column("marketplace_id", sa.Uuid(), nullable=False),
        sa.Column("condition", sa.String(length=20), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("metric_type", sa.String(length=30), nullable=False),
        sa.Column("value", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("source_payload", sa.JSON(), nullable=True),
        sa.Column("retrieval_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("value >= 0", name="value_non_negative"),
        sa.CheckConstraint("sample_size >= 0", name="sample_size_non_negative"),
        sa.CheckConstraint("currency = upper(currency)", name="currency_uppercase"),
        sa.CheckConstraint(
            "condition IN ('new', 'used_complete', 'incomplete')",
            name="condition_allowed",
        ),
        sa.CheckConstraint(
            "metric_type IN ('low', 'median', 'average', 'high', 'fair_market_value')",
            name="metric_type_allowed",
        ),
        sa.ForeignKeyConstraint(["lego_set_id"], ["lego_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["marketplace_id"], ["marketplaces.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "lego_set_id",
            "marketplace_id",
            "condition",
            "currency",
            "metric_type",
            "retrieval_time",
            name="uq_price_snapshot_metric_retrieval",
        ),
    )


def upgrade() -> None:
    bind = op.get_bind()
    legacy = sa.Table("price_snapshots", sa.MetaData(), autoload_with=bind)
    rows = bind.execute(sa.select(legacy)).mappings().all()
    op.rename_table("price_snapshots", "price_snapshots_legacy")
    _create_new_table()
    new = sa.table(
        "price_snapshots",
        sa.column("id", sa.Uuid()),
        sa.column("lego_set_id", sa.Uuid()),
        sa.column("marketplace_id", sa.Uuid()),
        sa.column("condition", sa.String()),
        sa.column("currency", sa.String()),
        sa.column("metric_type", sa.String()),
        sa.column("value", sa.Numeric(precision=12, scale=2)),
        sa.column("sample_size", sa.Integer()),
        sa.column("source_payload", sa.JSON()),
        sa.column("retrieval_time", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_price_snapshots_set_retrieval_time",
        "price_snapshots",
        ["lego_set_id", "retrieval_time"],
    )
    op.create_index(
        "ix_price_snapshots_set_condition_metric_retrieval",
        "price_snapshots",
        ["lego_set_id", "condition", "metric_type", "retrieval_time"],
    )
    op.create_index(
        "ix_price_snapshots_marketplace_condition_metric_retrieval",
        "price_snapshots",
        ["marketplace_id", "condition", "metric_type", "retrieval_time"],
    )

    migrated = []
    for row in rows:
        condition = (
            "new"
            if row["condition"] == "new"
            else "used_complete"
            if row["condition"] == "used"
            else "incomplete"
        )
        retrieval_time = row["snapshot_at"] or row["created_at"] or datetime.utcnow()
        for metric_type, legacy_column in _METRICS.items():
            value = row[legacy_column]
            if value is None:
                continue
            migrated.append(
                {
                    "id": uuid4(),
                    "lego_set_id": row["lego_set_id"],
                    "marketplace_id": row["marketplace_id"],
                    "condition": condition,
                    "currency": row["currency"],
                    "metric_type": metric_type,
                    "value": value,
                    "sample_size": row["listing_count"],
                    "source_payload": row["source_payload"],
                    "retrieval_time": retrieval_time,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
    if migrated:
        bind.execute(new.insert(), migrated)
    op.drop_table("price_snapshots_legacy")


def downgrade() -> None:
    raise NotImplementedError("metric price snapshots cannot be safely downgraded")
