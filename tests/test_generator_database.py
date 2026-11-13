"""Runs against the local Postgres from docker-compose; everything is rolled back."""

import random
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from dataforge.generator.database import connect, copy_rows, load_reference, simulate_activity
from dataforge.generator.orders import build_orders
from dataforge.generator.reference import Volumes, build_reference

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC).replace(microsecond=0)
SMALL = Volumes(customers=20, sellers=3, products=10, categories=3, offers=20)


@pytest.fixture
def conn():
    try:
        connection = connect()
    except psycopg.OperationalError:
        pytest.skip("Postgres is not running")
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def _seed(conn, rand_gen):
    reference = build_reference(rand_gen, SMALL, before=NOW - timedelta(days=30))
    # Unique emails, so the test also works on a database that already holds data.
    for table in ("manager", "customer"):
        for row in reference.tables[table]:
            row["email"] = f"test-{rand_gen.getrandbits(64):x}-{row['email']}"
    load_reference(conn, reference)
    orders, items = build_orders(rand_gen, reference.sources, 200, NOW - timedelta(days=30), NOW)
    copy_rows(conn, "orders", orders)
    copy_rows(conn, "order_item", [dict(item) for item in items])
    return orders, items


def test_generated_data_satisfies_all_constraints(conn):
    orders, items = _seed(conn, random.Random(1))
    ids = [order["id"] for order in orders]
    row = conn.execute("SELECT count(*) FROM orders WHERE id = ANY(%s)", (ids,)).fetchone()
    assert row is not None and row[0] == len(orders)


def test_activity_changes_rows_through_the_trigger(conn):
    _seed(conn, random.Random(2))
    started = conn.execute("SELECT now()").fetchone()
    counts = simulate_activity(conn, random.Random(2), new_orders=10, late_orders=3, deletes=1)
    assert counts["new orders"] == 10 and counts["late orders"] == 3
    # Inside one transaction now() is constant: every touched row carries exactly that value.
    assert started is not None
    touched = conn.execute(
        "SELECT count(*) FROM order_item WHERE updated_at = %s", (started[0],)
    ).fetchone()
    assert touched is not None and touched[0] > 0
