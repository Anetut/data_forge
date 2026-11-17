"""Read, write and parse CSV files for `OrderItemRow` objects.

Every value is text. An empty cell means null.
"""

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from dataforge.domain.enums import OrderStatus
from dataforge.domain.order_item_row import ORDER_ITEM_COLUMNS, OrderItemRow


class CsvFormat:
    suffix = ".csv"

    def write(self, file_path: Path, rows: list[OrderItemRow]) -> None:
        with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=ORDER_ITEM_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def read(self, file_path: Path) -> list[dict[str, str]]:
        """Loads CSV file content.

        All values are strings.
        Empty cells are empty strings."""
        with open(file_path, newline="", encoding="utf-8") as csv_file:
            return list(csv.DictReader(csv_file))

    def parse_row(self, raw_row: dict[str, str]) -> OrderItemRow:
        """Convert one CSV row into an `OrderItemRow`.

        Empty optional timestamps become None.
        Timestamps must carry a UTC offset; values without one are rejected.
        Raises ValueError for an invalid UUID, integer, status or timestamp.
        Raises decimal.InvalidOperation for invalid price.
        """
        return {
            "id": UUID(raw_row["id"]),
            "order_id": UUID(raw_row["order_id"]),
            "inventory_id": UUID(raw_row["inventory_id"]),
            "shipping_provider_id": UUID(raw_row["shipping_provider_id"]),
            "price_at_the_time": Decimal(raw_row["price_at_the_time"]),
            "discount_pct_at_the_time": int(raw_row["discount_pct_at_the_time"]),
            "order_status": OrderStatus(raw_row["order_status"]),
            "quantity": int(raw_row["quantity"]),
            "shipped_at": _parse_optional_datetime(raw_row["shipped_at"]),
            "delivered_at": _parse_optional_datetime(raw_row["delivered_at"]),
            "created_at": _parse_datetime(raw_row["created_at"]),
            "updated_at": _parse_datetime(raw_row["updated_at"]),
        }


def _parse_optional_datetime(value: str) -> datetime | None:
    if value:
        return _parse_datetime(value)
    return None


def _parse_datetime(value: str) -> datetime:
    parsed_date_time = datetime.fromisoformat(value)
    if parsed_date_time.tzinfo is None:
        raise ValueError(f"timestamp without a UTC offset: {value!r}")
    return parsed_date_time
