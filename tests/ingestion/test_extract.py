import random
from datetime import timedelta

import pyarrow as pa
import pytest

from dataforge.generator.data.orders import build_orders
from dataforge.generator.data.reference import Volumes, build_reference
from dataforge.generator.database.loading import copy_rows, load_reference
from dataforge.ingestion.extract import (
    ColumnInfo,
    _build_schema_from_column_types,
    _match_sql_data_type_to_arrow_type,
    extract_changes,
    extract_schema,
)


@pytest.mark.parametrize(
    ("udt_name", "expected"),
    [
        ("uuid", pa.string()),
        ("int4", pa.int32()),
        ("int2", pa.int16()),
        ("bool", pa.bool_()),
        ("timestamptz", pa.timestamp("us", tz="UTC")),
        ("date", pa.date32()),
        ("varchar", pa.string()),
        ("order_status_enum", pa.string()),
        ("payment_method_enum", pa.string()),
        ("payment_status_enum", pa.string()),
    ],
)
def test_postgres_types_map_to_arrow_types(udt_name, expected):
    assert _match_sql_data_type_to_arrow_type(udt_name, None, None) == expected


def test_numeric_keeps_declared_precision_and_scale():
    assert _match_sql_data_type_to_arrow_type("numeric", 10, 2) == pa.decimal128(10, 2)


def test_numeric_without_precision_is_rejected():
    with pytest.raises(ValueError, match="precision"):
        _match_sql_data_type_to_arrow_type("numeric", None, None)


def test_unknown_postgres_type_is_rejected():
    with pytest.raises(ValueError, match="jsonb"):
        _match_sql_data_type_to_arrow_type("jsonb", None, None)


def test_schema_keeps_column_names_and_order():
    columns: list[ColumnInfo] = [
        {"column_name": "id", "udt_name": "uuid", "numeric_precision": None, "numeric_scale": None},
        {
            "column_name": "price",
            "udt_name": "numeric",
            "numeric_precision": 10,
            "numeric_scale": 2,
        },
        {
            "column_name": "created_at",
            "udt_name": "timestamptz",
            "numeric_precision": None,
            "numeric_scale": None,
        },
    ]
    schema = _build_schema_from_column_types(columns)
    assert schema == pa.schema(
        [
            ("id", pa.string()),
            ("price", pa.decimal128(10, 2)),
            ("created_at", pa.timestamp("us", tz="UTC")),
        ]
    )


def test_schema_fails_loudly_on_an_unmapped_column():
    columns: list[ColumnInfo] = [
        {
            "column_name": "payload",
            "udt_name": "jsonb",
            "numeric_precision": None,
            "numeric_scale": None,
        }
    ]
    with pytest.raises(ValueError):
        _build_schema_from_column_types(columns)


# --- Against the local Postgres; every test rolls back, so no data is changed. ---


@pytest.fixture
def seeded(now, conn):
    """A few orders inside the test's transaction: some changed recently, some long ago."""
    rand_gen = random.Random(7)
    reference = build_reference(
        rand_gen, Volumes(customers=5, sellers=2, products=5, categories=2, offers=5), now
    )
    for table in ("manager", "customer"):  # unique emails, in case the database holds data
        for row in reference.tables[table]:
            row["email"] = f"extract-test-{rand_gen.getrandbits(64):x}-{row['email']}"
    load_reference(conn, reference)
    _, old_items = build_orders(
        rand_gen, reference.sources, 5, now - timedelta(days=60), now - timedelta(days=50)
    )
    _, new_items = build_orders(rand_gen, reference.sources, 5, now - timedelta(hours=2), now)
    old = [dict(item) | {"updated_at": now - timedelta(days=40)} for item in old_items]
    new = [dict(item) | {"updated_at": now - timedelta(minutes=30)} for item in new_items]
    orders = {item["order_id"]: item["created_at"] for item in old + new}
    copy_rows(
        conn,
        "orders",
        [
            {
                "id": order_id,
                "customer_id": reference.sources.customer_ids[0],
                "created_at": created_at,
                "updated_at": created_at,
            }
            for order_id, created_at in orders.items()
        ],
    )
    copy_rows(conn, "order_item", old + new)
    return {str(item["id"]) for item in old}, {str(item["id"]) for item in new}


def test_schema_of_order_item_matches_the_table_definition(conn):
    schema = extract_schema(conn, "order_item")
    assert schema.names[:4] == ["id", "order_id", "inventory_id", "shipping_provider_id"]
    assert schema.field("price_at_the_time").type == pa.decimal128(10, 2)
    assert schema.field("discount_pct_at_the_time").type == pa.int16()
    assert schema.field("quantity").type == pa.int32()
    assert schema.field("order_status").type == pa.string()
    assert schema.field("updated_at").type == pa.timestamp("us", tz="UTC")


def test_extract_returns_only_rows_changed_since(now, conn, seeded):
    old_ids, new_ids = seeded
    extracted = {
        str(row["id"]) for row in extract_changes(conn, "order_item", now - timedelta(hours=1))
    }
    assert new_ids <= extracted
    assert not old_ids & extracted


def test_extract_returns_rows_in_updated_at_order(now, conn, seeded):
    rows = extract_changes(conn, "order_item", now - timedelta(days=90))
    timestamps = [row["updated_at"] for row in rows]
    assert timestamps == sorted(timestamps)


def test_extract_returns_nothing_when_nothing_changed(now, conn, seeded):
    assert extract_changes(conn, "order_item", now + timedelta(days=1)) == []


def test_extract_without_watermark_returns_everything(conn, seeded):
    old_ids, new_ids = seeded
    extracted = {str(row["id"]) for row in extract_changes(conn, "order_item", None)}
    assert old_ids | new_ids <= extracted
