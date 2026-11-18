"""Command line: `python -m dataforge.generator [--seed N] COMMAND [options]`.

Commands: fill-db, activity, partner-feed (each described below).

Global option (before the command):
    --seed N          random seed, so the same command gives the same data (default 31).
                      Dates are relative to today, so they still move from day to day.

fill-db: fill an empty database with reference data and two years of orders.
    --orders N        orders created over the two years (default 30000)
    --scale X         multiply the orders and the shop's size: customers, sellers, products,
                      offers (default 1). Everything is built in memory: about 10 is the
                      practical limit on a laptop.

activity: one run of business changes, what an incremental extraction must pick up.
    --new-orders N    orders created since the newest existing one (default 300)
    --late-orders N   orders created days ago but inserted now (default 20)
    --deletes N       cancelled items to hard-delete, which updated_at can't reveal (default 5)

partner-feed: write a partner JSON Lines feed with data quality issues injected on purpose,
      plus a manifest listing every issue by line.
    --rows N          lines in the feed (default 5000)
    --issue-rate X    share of lines that get an injected issue (default 0.08)
    --out DIR         output directory (default data/feeds)

Example: python -m dataforge.generator --seed 7 activity --deletes 2
"""

import argparse
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg

from dataforge.generator.data.orders import build_orders
from dataforge.generator.data.reference import Volumes, build_reference
from dataforge.generator.database.activity import simulate_activity
from dataforge.generator.database.connection import PROJECT_ROOT, connect
from dataforge.generator.database.loading import copy_rows, is_empty, load_reference, read_sources
from dataforge.generator.partner_feed import build_feed, write_feed
from dataforge.generator.partner_feed.issues import DEFAULT_ISSUE_RATE

HISTORY = timedelta(days=730)


def main() -> None:
    args = _build_parser().parse_args()
    rand_gen = random.Random(args.seed)
    now = datetime.now(UTC).replace(microsecond=0)

    with connect() as conn:
        # Each command registered its own handler with `set_defaults(run=...)`.
        args.run(conn, rand_gen, now, args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dataforge.generator")
    parser.add_argument("--seed", type=int, default=31, help="random seed (dates follow today)")
    commands = parser.add_subparsers(required=True)
    _add_fill_db_command(commands)
    _add_activity_command(commands)
    _add_partner_feed_command(commands)
    return parser


def _add_fill_db_command(commands: argparse._SubParsersAction) -> None:
    fill_db = commands.add_parser(
        "fill-db",
        help="fill an empty database: reference data + 2 years of orders",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    fill_db.add_argument(
        "--orders", type=int, default=30_000, help="orders created over the two years"
    )
    fill_db.add_argument(
        "--scale",
        type=_positive_number,
        default=1.0,
        help="multiply the orders and the customers, sellers, products and offers",
    )
    fill_db.set_defaults(run=_run_fill_db)


def _add_activity_command(commands: argparse._SubParsersAction) -> None:
    activity = commands.add_parser(
        "activity",
        help="one run of changes: status updates, new and late orders, deletes",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    activity.add_argument(
        "--new-orders", type=int, default=300, help="orders created since the newest one"
    )
    activity.add_argument(
        "--late-orders", type=int, default=20, help="orders created days ago, inserted now"
    )
    activity.add_argument("--deletes", type=int, default=5, help="cancelled items to hard-delete")
    activity.set_defaults(run=_run_activity)


def _add_partner_feed_command(commands: argparse._SubParsersAction) -> None:
    feed = commands.add_parser(
        "partner-feed",
        help="write a partner JSON Lines feed with injected issues",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    feed.add_argument("--rows", type=int, default=5_000, help="lines in the feed")
    feed.add_argument(
        "--issue-rate",
        type=float,
        default=DEFAULT_ISSUE_RATE,
        help="share of lines that get an injected issue",
    )
    feed.add_argument(
        "--out", type=Path, default=PROJECT_ROOT / "data" / "feeds", help="output directory"
    )
    feed.set_defaults(run=_run_partner_feed)


def _run_fill_db(
    conn: psycopg.Connection, rand_gen: random.Random, now: datetime, args: argparse.Namespace
) -> None:
    if not is_empty(conn):
        raise SystemExit("Database is not empty. Recreate it: docker compose down -v && up -d")
    reference = build_reference(rand_gen, Volumes().scaled(args.scale), before=now - HISTORY)
    load_reference(conn, reference)
    order_count = round(args.orders * args.scale)
    orders, items = build_orders(rand_gen, reference.sources, order_count, now - HISTORY, now)
    copy_rows(conn, "orders", orders)
    copy_rows(conn, "order_item", [dict(item) for item in items])
    tables = {name: len(rows) for name, rows in reference.tables.items()}
    _report(tables | {"orders": len(orders), "order_item": len(items)})


def _run_activity(
    conn: psycopg.Connection, rand_gen: random.Random, now: datetime, args: argparse.Namespace
) -> None:
    # `now` is unused: every command handler takes the same arguments.
    _report(simulate_activity(conn, rand_gen, args.new_orders, args.late_orders, args.deletes))


def _run_partner_feed(
    conn: psycopg.Connection, rand_gen: random.Random, now: datetime, args: argparse.Namespace
) -> None:
    rows, manifest = build_feed(rand_gen, read_sources(conn), args.rows, now, args.issue_rate)
    path = write_feed(args.out, now, rows, manifest)
    _report({"rows": len(rows), "injected issues": len(manifest)})
    print(f"Feed: {path}")


def _positive_number(text: str) -> float:
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be greater than 0, got {text}")
    return value


def _report(counts: dict[str, int]) -> None:
    for name, count in counts.items():
        print(f"{name:>24}: {count:_}")


if __name__ == "__main__":
    main()
