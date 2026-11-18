"""Read, write and parse Parquet files for `OrderItemRow` objects.

Types come from the file's schema; only UUIDs and the status need converting.
"""

from pathlib import Path
from typing import Any
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from dataforge.domain.enums import OrderStatus
from dataforge.domain.order_item_row import OrderItemRow

ORDER_ITEM_SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("order_id", pa.string()),
        ("inventory_id", pa.string()),
        ("shipping_provider_id", pa.string()),
        ("price_at_the_time", pa.decimal128(10, 2)),
        ("discount_pct_at_the_time", pa.int16()),
        ("order_status", pa.string()),
        ("quantity", pa.int32()),
        ("shipped_at", pa.timestamp("us", tz="UTC")),
        ("delivered_at", pa.timestamp("us", tz="UTC")),
        ("created_at", pa.timestamp("us", tz="UTC")),
        ("updated_at", pa.timestamp("us", tz="UTC")),
    ]
)


class ParquetFormat:
    suffix = ".parquet"

    def write(self, file_path: Path, rows: list[OrderItemRow]) -> None:
        """Write a list of `OrderItemRow` objects to a Parquet file."""
        parquet_rows = [_to_parquet_row(row) for row in rows]
        table = pa.Table.from_pylist(parquet_rows, schema=ORDER_ITEM_SCHEMA)
        pq.write_table(table, file_path)

    def read(self, file_path: Path) -> list[dict[str, Any]]:
        """Read a Parquet file into one dict per row. Types come from the schema."""
        return pq.read_table(file_path).to_pylist()

    def parse_row(self, raw_row: dict[str, Any]) -> OrderItemRow:
        """Convert one Parquet row into an `OrderItemRow`."""
        return {
            "id": UUID(raw_row["id"]),
            "order_id": UUID(raw_row["order_id"]),
            "inventory_id": UUID(raw_row["inventory_id"]),
            "shipping_provider_id": UUID(raw_row["shipping_provider_id"]),
            "price_at_the_time": raw_row["price_at_the_time"],
            "discount_pct_at_the_time": raw_row["discount_pct_at_the_time"],
            "order_status": OrderStatus(raw_row["order_status"]),
            "quantity": raw_row["quantity"],
            "shipped_at": raw_row["shipped_at"],
            "delivered_at": raw_row["delivered_at"],
            "created_at": raw_row["created_at"],
            "updated_at": raw_row["updated_at"],
        }

    def read_columns(self, file_path: Path, columns: list[str]) -> list[dict[str, Any]]:
        """Read only the given columns; Parquet skips the others on disk."""
        return pq.read_table(file_path, columns=columns).to_pylist()


def _to_parquet_row(row: OrderItemRow) -> dict[str, object]:
    return {
        **row,
        "id": str(row["id"]),
        "order_id": str(row["order_id"]),
        "inventory_id": str(row["inventory_id"]),
        "shipping_provider_id": str(row["shipping_provider_id"]),
    }
