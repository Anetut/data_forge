from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest

from dataforge.domain.enums import OrderStatus
from dataforge.domain.order_item_row import ORDER_ITEM_COLUMNS, OrderItemRow
from dataforge.file_formats.parquet_format import ORDER_ITEM_SCHEMA, ParquetFormat


@pytest.fixture
def parquet_format() -> ParquetFormat:
    return ParquetFormat()


def test_parquet_schema_has_all_order_item_columns():
    assert ORDER_ITEM_SCHEMA.names == ORDER_ITEM_COLUMNS


def test_items_written_in_parquet(parquet_format, items, tmp_path):
    file_path = tmp_path / "items.parquet"
    parquet_format.write(file_path, items)
    assert len(parquet_format.read(file_path)) == len(items)


def test_parquet_round_trip_keeps_types(parquet_format, tmp_path, one_order_item_list):
    file_path = tmp_path / "items.parquet"
    parquet_format.write(file_path, one_order_item_list)
    file_content = parquet_format.read(file_path)
    assert file_content == [
        {
            "id": "240f16a7-6490-4d4a-8393-fd0e1cc62be5",
            "order_id": "b12f16a7-6490-4d4a-8393-fd0e1cc62be5",
            "inventory_id": "c12b65d7-d234-ca35-aa72-c12b65d7aa72",
            "shipping_provider_id": "d12c65d7-d234-cb35-a132-0c82a8d72d76",
            "price_at_the_time": Decimal("100.15"),
            "discount_pct_at_the_time": 0,
            "order_status": "Shipped",
            "quantity": 1,
            "shipped_at": datetime.fromisoformat("2024-01-02T00:00:00+00:00"),
            "delivered_at": None,
            "created_at": datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
            "updated_at": datetime.fromisoformat("2024-01-02T00:00:00+00:00"),
        }
    ]


def test_parquet_round_trip_returns_decimal_not_float(
    parquet_format, tmp_path, one_order_item_list
):
    file_path = tmp_path / "items.parquet"
    parquet_format.write(file_path, one_order_item_list)
    [row] = parquet_format.read(file_path)
    assert type(row["price_at_the_time"]) is Decimal


def test_parquet_round_trip_returns_aware_datetime(parquet_format, tmp_path, one_order_item_list):
    file_path = tmp_path / "items.parquet"
    parquet_format.write(file_path, one_order_item_list)
    [row] = parquet_format.read(file_path)
    assert row["created_at"].tzinfo is not None


@pytest.mark.parametrize(
    "column",
    ["id", "order_id", "inventory_id", "shipping_provider_id", "order_status"],
)
def test_parquet_round_trip_returns_str_for_uuid_and_enum(
    parquet_format, tmp_path, one_order_item_list, column
):
    file_path = tmp_path / "items.parquet"
    parquet_format.write(file_path, one_order_item_list)
    [row] = parquet_format.read(file_path)
    assert type(row[column]) is str


def test_write_parquet_rejects_price_with_more_than_two_decimals(
    parquet_format, tmp_path: Path, one_order_item_list: list[OrderItemRow]
) -> None:
    [row] = one_order_item_list
    bad_row: OrderItemRow = {**row, "price_at_the_time": Decimal("1.005")}
    with pytest.raises(pa.ArrowInvalid, match="data loss"):
        parquet_format.write(tmp_path / "items.parquet", [bad_row])


def test_write_parquet_rejects_price_exceeding_precision(
    parquet_format, tmp_path: Path, one_order_item_list: list[OrderItemRow]
) -> None:
    [row] = one_order_item_list
    bad_row: OrderItemRow = {**row, "price_at_the_time": Decimal("123456789.00")}
    with pytest.raises(pa.ArrowInvalid, match="precision"):
        parquet_format.write(tmp_path / "items.parquet", [bad_row])


def test_parse_parquet_row(parquet_format, tmp_path, one_order_item_list):
    file_path = tmp_path / "items.parquet"
    parquet_format.write(file_path, one_order_item_list)
    [raw_row] = parquet_format.read(file_path)
    assert parquet_format.parse_row(raw_row) == one_order_item_list[0]


def test_parse_parquet_row_restores_enum(parquet_format, tmp_path, one_order_item_list):
    file_path = tmp_path / "items.parquet"
    parquet_format.write(file_path, one_order_item_list)
    [raw_row] = parquet_format.read(file_path)
    assert parquet_format.parse_row(raw_row)["order_status"] is OrderStatus.SHIPPED


def test_parse_parquet_row_and_raises_error_for_unknown_enum_value(
    parquet_format, tmp_path, one_order_item_list
):
    file_path = tmp_path / "items.parquet"
    parquet_format.write(file_path, one_order_item_list)
    [raw_row] = parquet_format.read(file_path)
    raw_row["order_status"] = "Unknown"
    with pytest.raises(ValueError, match="Unknown"):
        parquet_format.parse_row(raw_row)


def test_read_parquet_columns_returns_only_requested_columns(parquet_format, items, tmp_path):
    file_path = tmp_path / "items.parquet"
    parquet_format.write(file_path, items)
    file_content = parquet_format.read_columns(file_path, ["id", "quantity"])
    assert len(file_content) == len(items)
    assert all(list(row) == ["id", "quantity"] for row in file_content)
