#!/usr/bin/env python3
# ruff: noqa: E402
"""Refresh one or more set valuations, skipping snapshots within freshness SLA."""

import argparse
import asyncio

from path_setup import ensure_backend_path

ensure_backend_path()

from flipradar.services.marketplace_service import (
    refresh_marketplace_data,
)  # noqa: E402, I001


async def _run(set_numbers: list[str], force: bool) -> int:
    refreshed = 0
    for set_number in set_numbers:
        snapshot = await refresh_marketplace_data(set_number, force=force)
        if snapshot is not None:
            refreshed += 1
            print(f"refreshed {set_number} at {snapshot.retrieval_time.isoformat()}")
        else:
            print(f"skipped {set_number}: snapshot is fresh")
    return refreshed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("set_numbers", nargs="+", help="LEGO set number(s) to refresh")
    parser.add_argument(
        "--force", action="store_true", help="Ignore freshness threshold"
    )
    args = parser.parse_args()
    refreshed = asyncio.run(_run(args.set_numbers, args.force))
    print(f"refresh complete: {refreshed}/{len(args.set_numbers)} set(s) updated")


if __name__ == "__main__":
    main()
