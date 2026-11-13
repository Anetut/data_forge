"""Command line: `python -m dataforge.generator {seed,activity,feed} [options]`."""

import argparse
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dataforge.generator.database import (
    PROJECT_ROOT,
    connect,
    copy_rows,
    is_empty,
    load_reference,
    read_sources,
    simulate_activity,
)
from dataforge.generator.feed import build_feed, write_feed
from dataforge.generator.orders import build_orders
from dataforge.generator.reference import Volumes, build_reference

HISTORY = timedelta(days=730)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m dataforge.generator")
    parser.add_argument("--seed", type=int, default=31, help="random seed (dates follow today)")
    commands = parser.add_subparsers(dest="command", required=True)

    seed = commands.add_parser(
        "seed", help="fill an empty database: reference data + 2 years of orders"
    )
    seed.add_argument("--orders", type=int, default=30_000)

    activity = commands.add_parser(
        "activity", help="one run of changes: updates, new, late, deletes"
    )
    activity.add_argument("--new-orders", type=int, default=300)
    activity.add_argument("--late-orders", type=int, default=20)
    activity.add_argument("--deletes", type=int, default=5)

    feed = commands.add_parser("feed", help="write a partner JSON Lines feed with injected issues")
    feed.add_argument("--rows", type=int, default=5_000)
    feed.add_argument("--issue-rate", type=float, default=0.08)
    feed.add_argument("--out", type=Path, default=PROJECT_ROOT / "data" / "feeds")

    args = parser.parse_args()
    rand_gen = random.Random(args.seed)
    now = datetime.now(UTC).replace(microsecond=0)

    with connect() as conn:
        if args.command == "seed":
            if not is_empty(conn):
                raise SystemExit(
                    "Database is not empty. Recreate it: docker compose down -v && up -d"
                )
            reference = build_reference(rand_gen, Volumes(), before=now - HISTORY)
            load_reference(conn, reference)
            orders, items = build_orders(
                rand_gen, reference.sources, args.orders, now - HISTORY, now
            )
            copy_rows(conn, "orders", orders)
            copy_rows(conn, "order_item", [dict(item) for item in items])
            tables = {name: len(rows) for name, rows in reference.tables.items()}
            _report(tables | {"orders": len(orders), "order_item": len(items)})
        elif args.command == "activity":
            _report(
                simulate_activity(conn, rand_gen, args.new_orders, args.late_orders, args.deletes)
            )
        else:
            rows, manifest = build_feed(
                rand_gen, read_sources(conn), args.rows, now, args.issue_rate
            )
            path = write_feed(args.out, now, rows, manifest)
            _report({"rows": len(rows), "injected issues": len(manifest)})
            print(f"Feed: {path}")


def _report(counts: dict[str, int]) -> None:
    for name, count in counts.items():
        print(f"{name:>24}: {count:_}")


if __name__ == "__main__":
    main()
