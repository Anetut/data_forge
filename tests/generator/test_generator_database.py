"""Runs against the local Postgres from docker-compose. Everything is rolled back."""

import random
from datetime import timedelta

from dataforge.generator.data.orders import build_orders
from dataforge.generator.data.reference import build_reference
from dataforge.generator.database.activity import simulate_activity
from dataforge.generator.database.loading import copy_rows, historic_load
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
    assert counts["late items"] >= counts["late orders"]
    # Inside one transaction now() is constant: every touched row carries exactly that value.
    assert started is not None
    touched = conn.execute(
        "SELECT count(*) FROM order_item WHERE updated_at = %s", (started[0],)
    ).fetchone()
    assert touched is not None and touched[0] > 0


def _insert_manager_returning_updated_at(conn, email, updated_at):
    row = conn.execute(
        "INSERT INTO manager (name, email, hire_date, updated_at) "
        "VALUES ('Historic Test', %s, current_date, %s) RETURNING updated_at",
        (email, updated_at),
    ).fetchone()
    assert row is not None
    return row[0]


def test_historic_load_keeps_updated_at_only_inside_the_block(conn, now):
    last_week = now - timedelta(days=7)
    with historic_load(conn):
        kept = _insert_manager_returning_updated_at(conn, "historic-in@example.com", last_week)
    after = _insert_manager_returning_updated_at(conn, "historic-out@example.com", last_week)
    assert kept == last_week
    assert after != last_week  # the triggers are back on after the block
