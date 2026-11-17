from dataforge.file_formats.csv_format import CsvFormat
from dataforge.format_benchmark import benchmark, find_changed_columns_after_round_trip


def test_benchmark_reports_the_round_trip(items, tmp_path):
    result = benchmark(CsvFormat(), tmp_path / "items.csv", items)

    assert result.suffix == ".csv"
    assert result.row_count == len(items)
    assert result.size_bytes > 0
    assert result.restored is True
    # CSV hands back text, so every column that isn't a string in the rows changes type.
    assert "quantity" in result.changed_columns
    assert "price_at_the_time" in result.changed_columns


def test_benchmark_leaves_no_warmup_file(items, tmp_path):
    benchmark(CsvFormat(), tmp_path / "items.csv", items)
    assert [path.name for path in tmp_path.iterdir()] == ["items.csv"]


def test_identical_rows_have_no_changed_columns(one_order_item_list):
    assert find_changed_columns_after_round_trip(one_order_item_list, one_order_item_list) == []


def test_changed_value_is_reported(one_order_item_list):
    [original] = one_order_item_list
    read_back = {**original, "quantity": 2}
    assert find_changed_columns_after_round_trip([original], [read_back]) == ["quantity"]


def test_changed_type_is_reported(one_order_item_list):
    [original] = one_order_item_list
    read_back = {**original, "order_status": "Shipped"}
    assert find_changed_columns_after_round_trip([original], [read_back]) == ["order_status"]


def test_changed_several_columns_are_sorted(one_order_item_list):
    [original] = one_order_item_list
    read_back = {
        **original,
        "id": "240f16a7-6490-4d4a-8393-fd0e1cc62be5",
        "discount_pct_at_the_time": "0",
    }
    assert find_changed_columns_after_round_trip([original], [read_back]) == [
        "discount_pct_at_the_time",
        "id",
    ]


def test_changed_more_of_same_column_is_reported_once(one_order_item_list):
    [original] = one_order_item_list
    changed = {**original, "quantity": 2}
    original_rows = [original, original, original]
    read_back_rows = [original, changed, changed]
    assert find_changed_columns_after_round_trip(original_rows, read_back_rows) == ["quantity"]
