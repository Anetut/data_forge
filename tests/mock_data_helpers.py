"""Helpers that insert generated rows into the test's transaction. Plain functions, not fixtures."""

import random
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from typing import Any

import psycopg

from dataforge.domain.order_item_row import OrderItemRow
from dataforge.generator.data.orders import build_orders
from dataforge.generator.data.reference import ReferenceData, Volumes, build_reference
from dataforge.generator.database.loading import copy_rows, historic_load, load_reference


def insert_reference_data_with_unique_emails(
    conn: psycopg.Connection, rand_gen: random.Random, reference: ReferenceData, prefix: str
) -> None:
    """Load reference data with unique emails, so tests also work on a database that holds data."""
    for table in ("manager", "customer"):
        for row in reference.tables[table]:
            row["email"] = f"{prefix}-{rand_gen.getrandbits(64):x}-{row['email']}"
    load_reference(conn, reference)


def insert_orders_for_order_items(
    conn: psycopg.Connection, items: Iterable[Mapping[str, Any]], customer_id: object
) -> None:
    """One `orders` row per distinct `order_id` in `items`, so the items' foreign keys resolve."""
    orders = {item["order_id"]: item["created_at"] for item in items}
    copy_rows(
        conn,
        "orders",
        [
            {
                "id": order_id,
                "customer_id": customer_id,
                "created_at": created_at,
                "updated_at": created_at,
            }
            for order_id, created_at in orders.items()
        ],
    )


def insert_old_and_recent_order_items(
    conn: psycopg.Connection, now: datetime
) -> tuple[list[OrderItemRow], list[OrderItemRow]]:
    """Five orders updated 40 days ago, five 30 minutes ago. Returns (old items, recent items)."""
    rand_gen = random.Random(7)
    reference = build_reference(
        rand_gen, Volumes(customers=5, sellers=2, products=5, categories=2, offers=5), now
    )
    insert_reference_data_with_unique_emails(conn, rand_gen, reference, "extract-test")
    _, old_items = build_orders(
        rand_gen, reference.sources, 5, now - timedelta(days=60), now - timedelta(days=50)
    )
    _, new_items = build_orders(rand_gen, reference.sources, 5, now - timedelta(hours=2), now)
    old: list[OrderItemRow] = [
        {**item, "updated_at": now - timedelta(days=40)} for item in old_items
    ]
    new: list[OrderItemRow] = [
        {**item, "updated_at": now - timedelta(minutes=30)} for item in new_items
    ]
    insert_orders_for_order_items(conn, old + new, reference.sources.customer_ids[0])
    # The tests choose updated_at on purpose; the database would otherwise set it to now().
    with historic_load(conn):
        copy_rows(conn, "order_item", old + new)
    return old, new


def insert_order_items_updated_at(
    conn: psycopg.Connection, times: list[datetime]
) -> list[OrderItemRow]:
    """One order item per timestamp, each with exactly that `updated_at`, in the given order."""
    rand_gen = random.Random(8)
    reference = build_reference(
        rand_gen, Volumes(customers=5, sellers=2, products=5, categories=2, offers=5), min(times)
    )
    insert_reference_data_with_unique_emails(conn, rand_gen, reference, "extract-test-times")
    _, items = build_orders(
        rand_gen, reference.sources, len(times), min(times) - timedelta(hours=1), min(times)
    )
    # An order can hold several items; keep the first of each, so there is one item per order.
    first_item_per_order: dict[object, OrderItemRow] = {}
    for item in items:
        first_item_per_order.setdefault(item["order_id"], item)
    rows: list[OrderItemRow] = [
        {**item, "updated_at": time}
        for item, time in zip(first_item_per_order.values(), times, strict=True)
    ]
    insert_orders_for_order_items(conn, rows, reference.sources.customer_ids[0])
    with historic_load(conn):
        copy_rows(conn, "order_item", rows)
    return rows
