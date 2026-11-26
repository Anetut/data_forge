"""One run of business activity on an existing database: what an extraction then has to pick up.

A run does four things, in this order:
1. moves some items to their next status (the `set_updated_at` trigger sets `updated_at`)
2. adds new orders, created since the newest existing one
3. adds late orders: created days ago, but inserted now (`updated_at` = now)
4. hard-deletes a few cancelled items, which an `updated_at` watermark cannot see
"""

import random
from datetime import UTC, datetime, timedelta
from typing import LiteralString
from uuid import UUID

import psycopg

from dataforge.domain.enums import OrderStatus
from dataforge.generator.data.orders import OrderSources, build_orders
from dataforge.generator.database.loading import copy_rows, read_sources

# Share of items that move to their next status in one run.
PROGRESS = {
    (OrderStatus.PENDING, OrderStatus.SHIPPED): 0.30,
    (OrderStatus.SHIPPED, OrderStatus.DELIVERED): 0.30,
    (OrderStatus.PENDING, OrderStatus.CANCELLED): 0.02,
    (OrderStatus.DELIVERED, OrderStatus.RETURNED): 0.002,
}

# The UPDATE for each new status. Shipping and delivering also set their timestamp.
_PROGRESS_SQL: dict[OrderStatus, LiteralString] = {
    OrderStatus.SHIPPED: (
        "UPDATE order_item SET order_status = %s, shipped_at = now() WHERE id = ANY(%s)"
    ),
    OrderStatus.DELIVERED: (
        "UPDATE order_item SET order_status = %s, delivered_at = now() WHERE id = ANY(%s)"
    ),
    OrderStatus.CANCELLED: "UPDATE order_item SET order_status = %s WHERE id = ANY(%s)",
    OrderStatus.RETURNED: "UPDATE order_item SET order_status = %s WHERE id = ANY(%s)",
}


def simulate_activity(
    conn: psycopg.Connection,
    rand_gen: random.Random,
    new_orders: int,
    late_orders: int,
    deletes: int,
) -> dict[str, int]:
    """One run of business activity. Returns what happened, by kind."""
    # The order of these steps is the order of random draws: changing it changes the data.
    now = datetime.now(UTC).replace(microsecond=0)
    counts = _progress_statuses(conn, rand_gen)
    sources = read_sources(conn)
    counts |= _insert_new_orders(conn, rand_gen, sources, new_orders, now)
    counts |= _insert_late_orders(conn, rand_gen, sources, late_orders, now)
    counts |= _delete_cancelled(conn, rand_gen, deletes)
    return counts


def _progress_statuses(conn: psycopg.Connection, rand_gen: random.Random) -> dict[str, int]:
    """Move some of the items forward in time to their next status.
    An item moves at most once per run."""
    # Read every candidate before the first update, so one update can't feed the next.
    candidates = {old: _item_ids(conn, old) for old, _ in PROGRESS}
    counts: dict[str, int] = {}
    already_moved: set[UUID] = set()
    for (old, new), share in PROGRESS.items():
        pool = [item_id for item_id in candidates[old] if item_id not in already_moved]
        moved = rand_gen.sample(pool, k=round(len(pool) * share))
        already_moved.update(moved)
        conn.execute(_PROGRESS_SQL[new], (new.value, moved))
        counts[f"{old.value} -> {new.value}"] = len(moved)
    return counts


def _insert_new_orders(
    conn: psycopg.Connection,
    rand_gen: random.Random,
    sources: OrderSources,
    count: int,
    now: datetime,
) -> dict[str, int]:
    """Orders created between the newest existing order and now."""
    newest = conn.execute("SELECT max(created_at) FROM orders").fetchone()
    start = newest[0] if newest and newest[0] else now - timedelta(days=1)
    orders, items = build_orders(rand_gen, sources, count, start, now)
    copy_rows(conn, "orders", orders)
    copy_rows(conn, "order_item", items)
    return {"new orders": len(orders), "new items": len(items)}


def _insert_late_orders(
    conn: psycopg.Connection,
    rand_gen: random.Random,
    sources: OrderSources,
    count: int,
    now: datetime,
) -> dict[str, int]:
    """Orders created 2-10 days ago that only reach the database now."""
    orders, items = build_orders(
        rand_gen, sources, count, now - timedelta(days=10), now - timedelta(days=2)
    )
    copy_rows(conn, "orders", [order | {"updated_at": now} for order in orders])
    copy_rows(conn, "order_item", [dict(item) | {"updated_at": now} for item in items])
    return {"late orders": len(orders), "late items": len(items)}


def _delete_cancelled(
    conn: psycopg.Connection, rand_gen: random.Random, count: int
) -> dict[str, int]:
    """Hard-delete a few cancelled items: no row is left behind to carry a new `updated_at`."""
    cancelled = _item_ids(conn, OrderStatus.CANCELLED)
    deleted = rand_gen.sample(cancelled, k=min(count, len(cancelled)))
    conn.execute("DELETE FROM order_item WHERE id = ANY(%s)", (deleted,))
    return {"hard deletes": len(deleted)}


def _item_ids(conn: psycopg.Connection, status: OrderStatus) -> list[UUID]:
    rows = conn.execute(
        "SELECT id FROM order_item WHERE order_status = %s ORDER BY id", (status.value,)
    )
    return [item_id for (item_id,) in rows]
