#!/usr/bin/env python3
# ruff: noqa: E402
"""Generate hourly portfolio valuation snapshots and apply retention."""

import argparse
import asyncio

from path_setup import ensure_backend_path

ensure_backend_path()

from flipradar.database import repositories  # noqa: E402, I001
from flipradar.database.session import SessionLocal  # noqa: E402, I001
from flipradar.services.portfolio_service import (
    create_user_valuation_snapshot,
)  # noqa: E402, I001
from flipradar.services.portfolio_valuation_retention import (  # noqa: E402, I001
    aggregate_and_prune_portfolio_valuations,
)


async def _run() -> tuple[int, int]:
    async with SessionLocal() as session:
        try:
            user_ids = await repositories.get_all_user_ids(session)
            for user_id in user_ids:
                await create_user_valuation_snapshot(session, user_id)
            pruned = await aggregate_and_prune_portfolio_valuations(session)
            await session.commit()
            return len(user_ids), pruned
        except Exception:
            await session.rollback()
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=0,
        help="Run repeatedly at this interval; omit for one scheduled invocation.",
    )
    args = parser.parse_args()
    if args.interval_minutes < 0:
        parser.error("--interval-minutes must be zero or greater")

    while True:
        users, pruned = asyncio.run(_run())
        print(
            f"portfolio snapshots processed for {users} user(s); "
            f"pruned {pruned} raw row(s)"
        )
        if args.interval_minutes == 0:
            return
        asyncio.run(asyncio.sleep(args.interval_minutes * 60))


if __name__ == "__main__":
    main()
