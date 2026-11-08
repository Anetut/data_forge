from dataforge.compare_formats_module import find_changed_columns_after_round_trip


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
