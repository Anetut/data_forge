"""Reads, writes and parses Parquet for OrderItemRow objects."""

from pathlib import Path
from typing import Any
from uuid import UUID

import pyarrow
import pyarrow.parquet

from dataforge.domain.enums import OrderStatus
from dataforge.domain.order_item_row import OrderItemRow

ORDER_ITEM_SCHEMA = pyarrow.schema(
    [
        ("id", pyarrow.string()),
        ("order_id", pyarrow.string()),
        ("inventory_id", pyarrow.string()),
        ("shipping_provider_id", pyarrow.string()),
        ("price_at_the_time", pyarrow.decimal128(10, 2)),
        ("discount_pct_at_the_time", pyarrow.int16()),
        ("order_status", pyarrow.string()),
        ("quantity", pyarrow.int32()),
        ("shipped_at", pyarrow.timestamp("us", tz="UTC")),
        ("delivered_at", pyarrow.timestamp("us", tz="UTC")),
        ("created_at", pyarrow.timestamp("us", tz="UTC")),
        ("updated_at", pyarrow.timestamp("us", tz="UTC")),
    ]
)

# This schema can be used to measure file size when treating uuids as binary
ORDER_ITEM_SCHEMA_BINARY_ID = pyarrow.schema(
    [
        ("id", pyarrow.binary(16)),
        ("order_id", pyarrow.binary(16)),
        ("inventory_id", pyarrow.binary(16)),
        ("shipping_provider_id", pyarrow.binary(16)),
        ("price_at_the_time", pyarrow.decimal128(10, 2)),
        ("discount_pct_at_the_time", pyarrow.int16()),
        ("order_status", pyarrow.string()),
        ("quantity", pyarrow.int32()),
        ("shipped_at", pyarrow.timestamp("us", tz="UTC")),
        ("delivered_at", pyarrow.timestamp("us", tz="UTC")),
        ("created_at", pyarrow.timestamp("us", tz="UTC")),
        ("updated_at", pyarrow.timestamp("us", tz="UTC")),
    ]
)


def write_parquet(file_path: Path, rows: list[OrderItemRow]) -> None:
    """Write a list of OrderItemRow objects to a Parquet file."""
    parquet_rows = [_to_parquet_row(row) for row in rows]
    table = pyarrow.Table.from_pylist(parquet_rows, schema=ORDER_ITEM_SCHEMA)
    pyarrow.parquet.write_table(table, file_path)


def read_parquet(file_path: Path) -> list[dict[str, Any]]:
    """Read a Parquet file into one dict per row. Types come from schema"""
    return pyarrow.parquet.read_table(file_path).to_pylist()


def read_parquet_columns(file_path: Path, columns: list[str]) -> list[dict[str, Any]]:
    """Read only the given columns; Parquet skips the others on disk."""
    return pyarrow.parquet.read_table(file_path, columns=columns).to_pylist()


def parse_parquet_row(row: dict[str, Any]) -> OrderItemRow:
    """Parse a Parquet row into an OrderItemRow object."""
    return {
        "id": UUID(row["id"]),
        "order_id": UUID(row["order_id"]),
        "inventory_id": UUID(row["inventory_id"]),
        "shipping_provider_id": UUID(row["shipping_provider_id"]),
        "price_at_the_time": row["price_at_the_time"],
        "discount_pct_at_the_time": row["discount_pct_at_the_time"],
        "order_status": OrderStatus(row["order_status"]),
        "quantity": row["quantity"],
        "shipped_at": row["shipped_at"],
        "delivered_at": row["delivered_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def write_parquet_file_with_binary_id(file_path: Path, rows: list[OrderItemRow]) -> None:
    """Write a list of OrderItemRow objects to a Parquet file."""
    parquet_rows = [_to_parquet_binary_uuid_row(row) for row in rows]
    table = pyarrow.Table.from_pylist(parquet_rows, schema=ORDER_ITEM_SCHEMA_BINARY_ID)
    pyarrow.parquet.write_table(table, file_path)


def parse_parquet_binary_id_row(row: dict[str, Any]) -> OrderItemRow:
    """Parse a Parquet row into an OrderItemRow object."""
    return {
        "id": UUID(bytes=row["id"]),
        "order_id": UUID(bytes=row["order_id"]),
        "inventory_id": UUID(bytes=row["inventory_id"]),
        "shipping_provider_id": UUID(bytes=row["shipping_provider_id"]),
        "price_at_the_time": row["price_at_the_time"],
        "discount_pct_at_the_time": row["discount_pct_at_the_time"],
        "order_status": OrderStatus(row["order_status"]),
        "quantity": row["quantity"],
        "shipped_at": row["shipped_at"],
        "delivered_at": row["delivered_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _to_parquet_row(row: OrderItemRow) -> dict[str, object]:
    return {
        **row,
        "id": str(row["id"]),
        "order_id": str(row["order_id"]),
        "inventory_id": str(row["inventory_id"]),
        "shipping_provider_id": str(row["shipping_provider_id"]),
    }


def _to_parquet_binary_uuid_row(row: OrderItemRow) -> dict[str, object]:
    return {
        **row,
        "id": row["id"].bytes,
        "order_id": row["order_id"].bytes,
        "inventory_id": row["inventory_id"].bytes,
        "shipping_provider_id": row["shipping_provider_id"].bytes,
    }
