"""Runs against the local Postgres from docker-compose. Everything is rolled back."""

import random
from datetime import timedelta

from dataforge.generator.data.orders import build_orders
from dataforge.generator.data.reference import build_reference
from dataforge.generator.database.activity import simulate_activity
from dataforge.generator.database.loading import copy_rows
from mock_data_helpers import insert_reference_data_with_unique_emails


def _seed(conn, rand_gen, now, volumes):
    reference = build_reference(rand_gen, volumes, before=now - timedelta(days=30))
    insert_reference_data_with_unique_emails(conn, rand_gen, reference, "test")
    orders, items = build_orders(rand_gen, reference.sources, 200, now - timedelta(days=30), now)
    copy_rows(conn, "orders", orders)
    copy_rows(conn, "order_item", [dict(item) for item in items])
    return orders, items


def test_generated_data_satisfies_all_constraints(conn, now, small_volumes):
    orders, items = _seed(conn, random.Random(1), now, small_volumes)
    ids = [order["id"] for order in orders]
    row = conn.execute("SELECT count(*) FROM orders WHERE id = ANY(%s)", (ids,)).fetchone()
    assert row is not None and row[0] == len(orders)


def test_activity_changes_rows_through_the_trigger(conn, now, small_volumes):
    _seed(conn, random.Random(2), now, small_volumes)
    started = conn.execute("SELECT now()").fetchone()
    counts = simulate_activity(conn, random.Random(2), new_orders=10, late_orders=3, deletes=1)
    assert counts["new orders"] == 10 and counts["late orders"] == 3
    # Inside one transaction now() is constant: every touched row carries exactly that value.
    assert started is not None
    touched = conn.execute(
        "SELECT count(*) FROM order_item WHERE updated_at = %s", (started[0],)
    ).fetchone()
    assert touched is not None and touched[0] > 0
