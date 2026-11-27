"""Write generated rows into Postgres, and read back what new orders can point to."""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Literal

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from dataforge.domain.enums import OrderStatus
from dataforge.generator.data.orders import OrderSources, StockedOffer
from dataforge.generator.data.reference import ReferenceData


def is_empty(conn: psycopg.Connection) -> bool:
    """True when no table in the public schema holds a single row."""
    tables = _get_db_tables(conn)
    checks = sql.SQL(" AND ").join(
        sql.SQL("NOT EXISTS (SELECT 1 FROM {})").format(sql.Identifier(table)) for table in tables
    )
    row = conn.execute(sql.SQL("SELECT {}").format(checks)).fetchone()
    return bool(row and row[0])


@contextmanager
def historic_load(conn: psycopg.Connection) -> Iterator[None]:
    """Rows written inside keep the `updated_at` they bring, instead of the database's now().

    For seeding a history and for tests only; normal writes never use it. It switches off the
    `set_updated_at` triggers for the current transaction, which locks those tables until it ends.
    """
    if conn.autocommit:
        # Each ALTER would commit on its own and switch the triggers off for every session.
        raise ValueError("historic_load needs a transaction, not an autocommit connection")
    triggers = conn.execute(
        "SELECT DISTINCT event_object_table, trigger_name FROM information_schema.triggers "
        "WHERE trigger_schema = 'public' AND action_statement = 'EXECUTE FUNCTION set_updated_at()'"
    ).fetchall()
    _set_triggers(conn, triggers, "DISABLE")
    try:
        yield
    finally:
        # After a database error the transaction can only roll back, which re-enables them anyway.
        if conn.info.transaction_status != TransactionStatus.INERROR:
            _set_triggers(conn, triggers, "ENABLE")


def _set_triggers(
    conn: psycopg.Connection, triggers: list[tuple[str, str]], action: Literal["DISABLE", "ENABLE"]
) -> None:
    for table, trigger in triggers:
        conn.execute(
            sql.SQL("ALTER TABLE {} {} TRIGGER {}").format(
                sql.Identifier(table), sql.SQL(action), sql.Identifier(trigger)
            )
        )


def load_reference(conn: psycopg.Connection, reference: ReferenceData) -> None:
    for table, rows in reference.tables.items():
        copy_rows(conn, table, rows)


def copy_rows(conn: psycopg.Connection, table: str, rows: Sequence[Mapping[str, object]]) -> None:
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
        customer_ids=[(row[0]) for row in customers],
        shipping_provider_ids=[row[0] for row in providers],
        stock=[StockedOffer(row[0], row[1], row[2]) for row in stock],
    )


def _db_value(value: object) -> object:
    # psycopg would send an Enum by its member name, but Postgres enums need the value.
    if isinstance(value, OrderStatus):
        return value.value
    return value


def _get_db_tables(conn: psycopg.Connection) -> list:
    return [
        name
        for (name,) in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            # Flyway's migration history, not shop data.
            "AND table_name <> 'flyway_schema_history'"
        )
    ]
