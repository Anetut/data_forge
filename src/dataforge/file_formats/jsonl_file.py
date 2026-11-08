"""Reads and writes and parses JSON Lines files for OrderItemRow objects."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from dataforge.domain.enums import OrderStatus
from dataforge.domain.order_item_row import OrderItemRow


def write_jsonl(file_path: Path, rows: list[OrderItemRow]) -> None:
    """Write a list of OrderItemRow objects to a JSONl file."""
    with open(file_path, "w", newline="", encoding="utf-8") as jsonl_file:
        for row in rows:
            jsonl_file.write(json.dumps(row, default=_to_jsonl_value) + "\n")


def read_jsonl(file_path: Path) -> list[dict[str, object]]:
    """Read a Jsonl file into one dict per row."""
    with open(file_path, newline="", encoding="utf-8") as jsonl_file:
        return [json.loads(line) for line in jsonl_file]


def parse_jsonl_row(raw_row: dict[str, object]) -> OrderItemRow:
    """Parse a JSONl row into an OrderItemRow object."""
    return {
        "id": _parse_id_value("id", raw_row["id"]),
        "order_id": _parse_id_value("order_id", raw_row["order_id"]),
        "inventory_id": _parse_id_value("inventory_id", raw_row["inventory_id"]),
        "shipping_provider_id": _parse_id_value(
            "shipping_provider_id", raw_row["shipping_provider_id"]
        ),
        "price_at_the_time": _parse_decimal_value(
            "price_at_the_time", raw_row["price_at_the_time"]
        ),
        "discount_pct_at_the_time": _parse_int_value(
            "discount_pct_at_the_time", raw_row["discount_pct_at_the_time"]
        ),
        "order_status": OrderStatus(raw_row["order_status"]),
        "quantity": _parse_int_value("quantity", raw_row["quantity"]),
        "shipped_at": _parse_optional_datetime("shipped_at", raw_row["shipped_at"]),
        "delivered_at": _parse_optional_datetime("delivered_at", raw_row["delivered_at"]),
        "created_at": _parse_datetime("created_at", raw_row["created_at"]),
        "updated_at": _parse_datetime("updated_at", raw_row["updated_at"]),
    }


def _to_jsonl_value(value: object) -> object:
    # Floats stores numbers in binary and decimals store digits:
    # Converting from float to decimals can add unwanted fraction digits
    # So we use strings
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(f"naive datetime {value!r}: timestamps must carry a UTC offset")
        return value.astimezone(UTC).isoformat()
    raise TypeError(f"Cannot write {type(value).__name__} to JSON")


def _parse_id_value(key: str, value: object) -> UUID:
    if not isinstance(value, str):
        raise TypeError(f"{key} must be str, got {type(value).__name__}")
    return UUID(value)


def _parse_decimal_value(key: str, value: object) -> Decimal:
    if not isinstance(value, str):
        raise TypeError(f"{key} must be str, got {type(value).__name__}")
    return Decimal(value)


def _parse_int_value(key: str, value: object) -> int:
    if type(value) is not int:
        raise TypeError(f"{key} must be int, got {type(value).__name__}")
    return value


def _parse_optional_datetime(key: str, value: object | None) -> datetime | None:
    if value is not None:
        return _parse_datetime(key, value)
    return None


def _parse_datetime(key: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{key} must be str, got {type(value).__name__}")
    parsed_date_time = datetime.fromisoformat(value)
    if parsed_date_time.tzinfo is None:
        raise ValueError(f"{key} has no UTC offset: {value!r}")
    return parsed_date_time
