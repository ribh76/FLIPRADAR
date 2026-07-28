#!/usr/bin/env python3
"""Delete price snapshots outside the configured retention window."""

import asyncio

from path_setup import ensure_backend_path

ensure_backend_path()

from flipradar.database.session import SessionLocal  # noqa: E402, I001
from flipradar.services.price_snapshot_retention import (  # noqa: E402
    prune_expired_price_snapshots,
)


async def _run() -> int:
    async with SessionLocal() as session:
        try:
            deleted = await prune_expired_price_snapshots(session)
            await session.commit()
            return deleted
        except Exception:
            await session.rollback()
            raise


def main() -> None:
    deleted = asyncio.run(_run())
    print(f"pruned {deleted} expired price snapshot(s)")


if __name__ == "__main__":
    main()
