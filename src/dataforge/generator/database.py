"""Load generated data into Postgres and simulate activity on it over time."""

import os
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import LiteralString

import psycopg
from psycopg import sql

from dataforge.domain.enums import OrderStatus
from dataforge.generator.orders import OrderSources, Row, StockedOffer, build_orders
from dataforge.generator.reference import ReferenceData

# Share of items that move to their next status in one activity run.
PROGRESS = {
    (OrderStatus.PENDING, OrderStatus.SHIPPED): 0.30,
    (OrderStatus.SHIPPED, OrderStatus.DELIVERED): 0.30,
    (OrderStatus.PENDING, OrderStatus.CANCELLED): 0.02,
    (OrderStatus.DELIVERED, OrderStatus.RETURNED): 0.002,
}


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def connect() -> psycopg.Connection:
    """Connect with the settings docker-compose uses: environment, then `.env`, then defaults."""
    settings = _read_env_file(PROJECT_ROOT / ".env") | os.environ

    def setting(name: str, default: str) -> str:
        return settings.get(name, default)

    return psycopg.connect(
        host=setting("POSTGRES_HOST", "localhost"),
        port=int(setting("POSTGRES_PORT", "5432")),
        user=setting("POSTGRES_USER", "dataforge"),
        password=setting("POSTGRES_PASSWORD", "dataforge_local_only"),
        dbname=setting("POSTGRES_DB", "dataforge"),
    )


def _read_env_file(path: Path) -> dict[str, str]:
    """KEY=value lines; comments and blank lines skipped. Enough for this project's .env."""
    if not path.exists():
        return {}
    pairs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and not key.strip().startswith("#"):
            pairs[key.strip()] = value.strip()
    return pairs


def is_empty(conn: psycopg.Connection) -> bool:
    row = conn.execute("SELECT NOT EXISTS (SELECT 1 FROM manager)").fetchone()
    return bool(row and row[0])


def load_reference(conn: psycopg.Connection, reference: ReferenceData) -> None:
    for table, rows in reference.tables.items():
        copy_rows(conn, table, rows)


def copy_rows(conn: psycopg.Connection, table: str, rows: list[Row]) -> None:
    """Bulk insert with COPY: one round trip instead of one INSERT per row."""
    if not rows:
        return
    columns = list(rows[0])
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    with conn.cursor() as cursor, cursor.copy(statement) as copy:
        for row in rows:
            copy.write_row([_db_value(row[column]) for column in columns])


def read_sources(conn: psycopg.Connection) -> OrderSources:
    """What new orders can point to, read back from the database."""
    customers = conn.execute("SELECT id FROM customer ORDER BY id").fetchall()
    providers = conn.execute("SELECT id FROM shipping_provider ORDER BY id").fetchall()
    stock = conn.execute(
        "SELECT i.id, o.price, o.discount_pct FROM inventory i JOIN offer o ON o.id = i.offer_id "
        "ORDER BY i.id"
    ).fetchall()
    return OrderSources(
        customer_ids=[row[0] for row in customers],
        shipping_provider_ids=[row[0] for row in providers],
        stock=[StockedOffer(row[0], row[1], row[2]) for row in stock],
    )


def simulate_activity(
    conn: psycopg.Connection,
    rand_gen: random.Random,
    new_orders: int,
    late_orders: int,
    deletes: int,
) -> dict[str, int]:
    """One run of business activity. Returns what happened, by kind.

    - status changes: the `set_updated_at` trigger moves `updated_at` to now()
    - new orders since the newest existing one
    - late orders: created days ago, inserted now (`updated_at` = now)
    - hard deletes of cancelled items: invisible to an `updated_at` watermark
    """
    now = datetime.now(UTC).replace(microsecond=0)
    counts: dict[str, int] = {}

    candidates = {
        status: [
            row[0]
            for row in conn.execute(
                "SELECT id FROM order_item WHERE order_status = %s ORDER BY id", (status.value,)
            )
        ]
        for status in {old for old, _ in PROGRESS}
    }
    already_moved: set = set()
    for (old, new), share in PROGRESS.items():
        pool = [item_id for item_id in candidates[old] if item_id not in already_moved]
        moved = rand_gen.sample(pool, k=round(len(pool) * share))
        already_moved.update(moved)
        conn.execute(_PROGRESS_SQL[new], (new.value, moved))
        counts[f"{old.value} -> {new.value}"] = len(moved)

    newest = conn.execute("SELECT max(created_at) FROM orders").fetchone()
    start = newest[0] if newest and newest[0] else now - timedelta(days=1)
    sources = read_sources(conn)
    orders, items = build_orders(rand_gen, sources, new_orders, start, now)
    copy_rows(conn, "orders", orders)
    copy_rows(conn, "order_item", list(map(dict, items)))
    counts["new orders"] = len(orders)
    counts["new items"] = len(items)

    late, late_items = build_orders(
        rand_gen, sources, late_orders, now - timedelta(days=10), now - timedelta(days=2)
    )
    copy_rows(conn, "orders", [order | {"updated_at": now} for order in late])
    copy_rows(conn, "order_item", [dict(item) | {"updated_at": now} for item in late_items])
    counts["late orders"] = len(late)

    cancelled = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM order_item WHERE order_status = 'Cancelled' ORDER BY id"
        )
    ]
    deleted = rand_gen.sample(cancelled, k=min(deletes, len(cancelled)))
    conn.execute("DELETE FROM order_item WHERE id = ANY(%s)", (deleted,))
    counts["hard deletes"] = len(deleted)
    return counts


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


def _db_value(value: object) -> object:
    # psycopg would dump an Enum by member name; Postgres enums need the value.
    if isinstance(value, OrderStatus):
        return value.value
    return value
