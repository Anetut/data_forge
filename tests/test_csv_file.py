from datetime import datetime
from decimal import Decimal
from uuid import UUID

import pytest

from dataforge.domain.enums import OrderStatus
from dataforge.file_formats.csv_file import parse_csv_row, read_csv, write_csv


def test_items_written_in_csv(items, tmp_path):
    csv_file = tmp_path / "items.csv"
    write_csv(csv_file, items)

    assert len(read_csv(csv_file)) == len(items)


def test_item_types_in_csv(tmp_path, one_order_item_list):
    file_path = tmp_path / "items.csv"

    write_csv(file_path, one_order_item_list)
    with open(file_path, encoding="utf-8") as csv_file:
        lines = csv_file.readlines()
    assert (
        lines[0] == "id,order_id,inventory_id,shipping_provider_id,price_at_the_time,"
        "discount_pct_at_the_time,order_status,quantity,shipped_at,delivered_at,created_at,updated_at\n"
    )

    assert (
        lines[1] == "240f16a7-6490-4d4a-8393-fd0e1cc62be5,b12f16a7-6490-4d4a-8393-fd0e1cc62be5,"
        "c12b65d7-d234-ca35-aa72-c12b65d7aa72,d12c65d7-d234-cb35-a132-0c82a8d72d76,100.15,0,Shipped,"
        "1,2024-01-02 00:00:00+00:00,,2024-01-01 00:00:00+00:00,2024-01-02 00:00:00+00:00\n"
    )


def test_csv_round_trip_returns_strings(tmp_path, one_order_item_list):
    write_csv(tmp_path / "items.csv", one_order_item_list)
    file_content = read_csv(tmp_path / "items.csv")
    assert file_content == [
        {
            "id": "240f16a7-6490-4d4a-8393-fd0e1cc62be5",
            "order_id": "b12f16a7-6490-4d4a-8393-fd0e1cc62be5",
            "inventory_id": "c12b65d7-d234-ca35-aa72-c12b65d7aa72",
            "shipping_provider_id": "d12c65d7-d234-cb35-a132-0c82a8d72d76",
            "price_at_the_time": "100.15",
            "discount_pct_at_the_time": "0",
            "order_status": "Shipped",
            "quantity": "1",
            "shipped_at": "2024-01-02 00:00:00+00:00",
            "delivered_at": "",
            "created_at": "2024-01-01 00:00:00+00:00",
            "updated_at": "2024-01-02 00:00:00+00:00",
        }
    ]


def test_parse_csv_row(raw_csv_row):
    parsed_row = parse_csv_row(raw_csv_row)
    assert parsed_row == {
        "id": UUID("240f16a7-6490-4d4a-8393-fd0e1cc62be5"),
        "order_id": UUID("b12f16a7-6490-4d4a-8393-fd0e1cc62be5"),
        "inventory_id": UUID("c12b65d7-d234-ca35-aa72-c12b65d7aa72"),
        "shipping_provider_id": UUID("d12c65d7-d234-cb35-a132-0c82a8d72d76"),
        "price_at_the_time": Decimal("100.15"),
        "discount_pct_at_the_time": 10,
        "order_status": OrderStatus.SHIPPED,
        "quantity": 1,
        "shipped_at": datetime.fromisoformat("2024-01-02 00:00:00+00:00"),
        "delivered_at": datetime.fromisoformat("2024-02-02 00:00:00+00:00"),
        "created_at": datetime.fromisoformat("2024-01-01 00:00:00+00:00"),
        "updated_at": datetime.fromisoformat("2024-02-02 00:00:00+00:00"),
    }


def test_parse_csv_row_with_0_discount(raw_csv_row):
    raw_csv_row["discount_pct_at_the_time"] = "0"
    parsed_row = parse_csv_row(raw_csv_row)
    assert parsed_row["discount_pct_at_the_time"] == 0


@pytest.mark.parametrize(
    "column",
    ["shipped_at", "delivered_at"],
)
def test_parse_csv_row_with_null_dates(raw_csv_row, column):
    raw_csv_row[column] = ""
    parsed_row = parse_csv_row(raw_csv_row)
    assert parsed_row[column] is None


@pytest.mark.parametrize(
    "column",
    ["shipped_at", "delivered_at", "updated_at", "created_at"],
)
def test_parse_csv_row_rejects_datetime_without_offset(raw_csv_row, column):
    raw_csv_row[column] = "2024-01-02 00:00:00"
    with pytest.raises(ValueError, match="without a UTC offset"):
        parse_csv_row(raw_csv_row)


def test_parse_csv_row_and_raises_error_for_unknown_enum_value(raw_csv_row):
    raw_csv_row["order_status"] = "Unknown"
    with pytest.raises(ValueError, match="Unknown"):
        parse_csv_row(raw_csv_row)


def test_parse_csv_row_for_batch_data_round_trip(items, tmp_path):
    write_csv(tmp_path / "items.csv", items)
    file_content = read_csv(tmp_path / "items.csv")
    parsed_rows = [parse_csv_row(raw_row) for raw_row in file_content]
    assert parsed_rows == items


def test_parse_csv_row_for_empty_file(tmp_path):
    write_csv(tmp_path / "items.csv", [])
    file_content = read_csv(tmp_path / "items.csv")
    parsed_rows = [parse_csv_row(raw_row) for raw_row in file_content]
    assert parsed_rows == []
