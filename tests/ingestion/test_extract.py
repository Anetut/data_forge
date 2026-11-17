from datetime import timedelta

import pyarrow as pa
import pytest

from dataforge.ingestion.extract import (
    BUFFER_TIME,
    ColumnInfo,
    _build_schema_from_column_types,
    _match_sql_data_type_to_arrow_type,
    extract_changes,
    extract_schema,
)
from mock_data_helpers import insert_old_and_recent_order_items, insert_order_items_updated_at


@pytest.fixture
def old_and_recent_item_ids(now, conn):
    """Old and recent order items inside the test's transaction: (old ids, recent ids)."""
    old_items, new_items = insert_old_and_recent_order_items(conn, now)
    return {str(item["id"]) for item in old_items}, {str(item["id"]) for item in new_items}


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


def test_schema_of_order_item_matches_the_table_definition(conn):
    schema = extract_schema(conn, "order_item")
    assert schema.names[:4] == ["id", "order_id", "inventory_id", "shipping_provider_id"]
    assert schema.field("price_at_the_time").type == pa.decimal128(10, 2)
    assert schema.field("discount_pct_at_the_time").type == pa.int16()
    assert schema.field("quantity").type == pa.int32()
    assert schema.field("order_status").type == pa.string()
    assert schema.field("updated_at").type == pa.timestamp("us", tz="UTC")


def test_extract_returns_only_rows_changed_since(now, conn, old_and_recent_item_ids):
    old_ids, new_ids = old_and_recent_item_ids
    extracted = {
        str(row["id"]) for row in extract_changes(conn, "order_item", now - timedelta(hours=1))
    }
    assert new_ids <= extracted
    assert not old_ids & extracted


def test_extract_returns_rows_in_updated_at_order(now, conn, old_and_recent_item_ids):
    old_ids, new_ids = old_and_recent_item_ids
    rows = extract_changes(conn, "order_item", now - timedelta(days=90))
    timestamps = [row["updated_at"] for row in rows]
    assert timestamps == sorted(timestamps)


def test_extract_returns_nothing_when_nothing_changed(now, conn, old_and_recent_item_ids):
    old_ids, new_ids = old_and_recent_item_ids
    assert extract_changes(conn, "order_item", now + timedelta(days=1)) == []


def test_extract_without_watermark_returns_everything(conn, old_and_recent_item_ids):
    old_ids, new_ids = old_and_recent_item_ids
    extracted = {str(row["id"]) for row in extract_changes(conn, "order_item", None)}
    assert old_ids | new_ids <= extracted


def test_extract_rereads_the_buffer_before_the_watermark(now, conn):
    """Rows up to BUFFER_TIME older than the watermark come back; older ones don't."""
    watermark = now - timedelta(minutes=10)
    since = watermark - BUFFER_TIME
    too_old, at_since, inside_buffer, after_watermark = insert_order_items_updated_at(
        conn,
        [
            since - timedelta(minutes=5),
            since,  # `updated_at > since` is strict, so a row exactly at the boundary is skipped
            watermark - timedelta(minutes=5),  # older than the watermark: a late commit
            watermark + timedelta(minutes=5),
        ],
    )
    extracted = [str(row["id"]) for row in extract_changes(conn, "order_item", watermark)]
    assert extracted == [str(inside_buffer["id"]), str(after_watermark["id"])]
    assert str(too_old["id"]) not in extracted
    assert str(at_since["id"]) not in extracted
