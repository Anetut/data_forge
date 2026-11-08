import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from dataforge.domain.order_item_row import OrderItemRow
from dataforge.file_formats.jsonl_file import parse_jsonl_row, read_jsonl, write_jsonl


def test_items_written_in_jsonl(items, tmp_path):
    jsonl_file = tmp_path / "items.jsonl"
    write_jsonl(jsonl_file, items)
    assert len(read_jsonl(jsonl_file)) == len(items)


def test_item_round_trip_in_jsonl(one_order_item_list, tmp_path):
    file_path = tmp_path / "items.jsonl"
    write_jsonl(file_path, one_order_item_list)
    with open(file_path, encoding="utf-8") as jsonl_file:
        [line] = jsonl_file.readlines()

    assert json.loads(line) == {
        "id": "240f16a7-6490-4d4a-8393-fd0e1cc62be5",
        "order_id": "b12f16a7-6490-4d4a-8393-fd0e1cc62be5",
        "inventory_id": "c12b65d7-d234-ca35-aa72-c12b65d7aa72",
        "shipping_provider_id": "d12c65d7-d234-cb35-a132-0c82a8d72d76",
        "price_at_the_time": "100.15",
        "discount_pct_at_the_time": 0,
        "order_status": "Shipped",
        "quantity": 1,
        "shipped_at": "2024-01-02T00:00:00+00:00",
        "delivered_at": None,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-02T00:00:00+00:00",
    }
    assert line.count('"delivered_at": null') > 0


def test_parse_jsonl_row_rejects_none_in_id(raw_jsonl_row):
    raw_jsonl_row["id"] = None
    with pytest.raises(TypeError, match="id must be str, got NoneType"):
        parse_jsonl_row(raw_jsonl_row)


def test_parse_jsonl_row_rejects_bool_as_int(raw_jsonl_row):
    raw_jsonl_row["quantity"] = True
    with pytest.raises(TypeError, match="quantity must be int, got bool"):
        parse_jsonl_row(raw_jsonl_row)


@pytest.mark.parametrize(
    "column",
    ["shipped_at", "delivered_at"],
)
def test_parse_jsonl_row_keeps_null_as_none(raw_jsonl_row, column):
    raw_jsonl_row[column] = None
    parsed_row = parse_jsonl_row(raw_jsonl_row)
    assert parsed_row[column] is None


def test_parse_jsonl_row_with_0_discount(raw_jsonl_row):
    raw_jsonl_row["discount_pct_at_the_time"] = 0
    parsed_row = parse_jsonl_row(raw_jsonl_row)
    assert parsed_row["discount_pct_at_the_time"] == 0


def test_parse_jsonl_row_with_price_at_the_time(raw_jsonl_row):
    raw_jsonl_row["price_at_the_time"] = "10.15"
    parsed_row = parse_jsonl_row(raw_jsonl_row)
    assert parsed_row["price_at_the_time"] == Decimal("10.15")


@pytest.mark.parametrize(
    "column",
    ["quantity", "discount_pct_at_the_time"],
)
def test_parse_jsonl_row_int(raw_jsonl_row, column):
    raw_jsonl_row[column] = 10
    parsed_row = parse_jsonl_row(raw_jsonl_row)
    assert parsed_row[column] == 10


@pytest.mark.parametrize(
    "column",
    ["shipped_at", "delivered_at", "updated_at", "created_at"],
)
def test_parse_jsonl_row_rejects_datetime_without_offset(raw_jsonl_row, column):
    raw_jsonl_row[column] = "2024-01-02 00:00:00"
    with pytest.raises(ValueError, match=f"{column} has no UTC offset"):
        parse_jsonl_row(raw_jsonl_row)


def test_write_jsonl_rejects_naive_datetime(
    one_order_item_list: list[OrderItemRow], tmp_path: Path
):
    [row] = one_order_item_list
    naive_row: OrderItemRow = {**row, "created_at": datetime(2024, 1, 2, 10, 30)}  # no tzinfo
    with pytest.raises(ValueError, match="naive datetime"):
        write_jsonl(tmp_path / "items.jsonl", [naive_row])


def test_write_jsonl_converts_other_offsets_to_utc(
    one_order_item_list: list[OrderItemRow], tmp_path: Path
):
    [row] = one_order_item_list
    plus_two = timezone(timedelta(hours=2))
    shifted_row: OrderItemRow = {**row, "created_at": datetime(2024, 1, 2, 10, 30, tzinfo=plus_two)}
    file_path = tmp_path / "items.jsonl"
    write_jsonl(file_path, [shifted_row])
    assert '"created_at": "2024-01-02T08:30:00+00:00"' in file_path.read_text(encoding="utf-8")


def test_parse_jsonl_row_and_raises_error_for_unknown_enum_value(raw_jsonl_row):
    raw_jsonl_row["order_status"] = "Unknown"
    with pytest.raises(ValueError, match="Unknown"):
        parse_jsonl_row(raw_jsonl_row)


def test_parse_jsonl_row_for_batch_data_round_trip(items, tmp_path):
    write_jsonl(tmp_path / "items.jsonl", items)
    file_content = read_jsonl(tmp_path / "items.jsonl")
    parsed_rows = [parse_jsonl_row(raw_row) for raw_row in file_content]
    assert parsed_rows == items


def test_parse_jsonl_row_for_empty_file(tmp_path):
    write_jsonl(tmp_path / "items.jsonl", [])
    file_content = read_jsonl(tmp_path / "items.jsonl")
    parsed_rows = [parse_jsonl_row(raw_row) for raw_row in file_content]
    assert parsed_rows == []


def test_parse_jsonl_row_rejects_none_in_required_column(raw_jsonl_row):
    raw_jsonl_row["created_at"] = None
    with pytest.raises(TypeError, match="created_at must be str, got NoneType"):
        parse_jsonl_row(raw_jsonl_row)
