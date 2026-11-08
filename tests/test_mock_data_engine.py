from decimal import Decimal
from uuid import UUID

from dataforge.domain.enums import OrderStatus
from dataforge.mock_data_engine import build_order_items


def test_id_is_unique(rng, items):
    ids = set()
    for item in items:
        assert item["id"] is not None
        assert item["id"] not in ids
        ids.add(item["id"])


def test_ids_types(rng, items):
    assert all(isinstance(item["id"], UUID) for item in items)
    assert all(isinstance(item["order_id"], UUID) for item in items)
    assert all(isinstance(item["inventory_id"], UUID) for item in items)
    assert all(isinstance(item["shipping_provider_id"], UUID) for item in items)


def test_price_format(rng, items):
    for item in items:
        assert item["price_at_the_time"] > 0
        assert (
            isinstance(item["price_at_the_time"], Decimal)
            and item["price_at_the_time"].as_tuple().exponent == -2
        )  # has exactly 2 decimals e.g. 1.00, 12.05, 100.99


def test_discount_pct_at_the_time_format(rng, items):
    for item in items:
        assert item["discount_pct_at_the_time"] is not None
        assert item["discount_pct_at_the_time"] >= 0
        assert isinstance(item["discount_pct_at_the_time"], int)
        assert item["discount_pct_at_the_time"] < 100
        assert (item["discount_pct_at_the_time"] % 5) == 0


def test_order_status_value(rng, items):
    for item in items:
        assert item["order_status"] in [member.value for member in OrderStatus]


def test_quantity_is_positive_integer(rng, items):
    for item in items:
        assert item["quantity"] > 0
        assert Decimal(item["quantity"]).as_tuple().exponent == 0  # has no decimals e.g. 1, 12, 100


def test_shipping_and_delivery_dates(rng, items):
    for item in items:
        match item["order_status"]:
            # test that delivered items were shipped first
            case OrderStatus.DELIVERED:
                assert item["shipped_at"] is not None
                assert item["delivered_at"] is not None
                assert item["delivered_at"] >= item["shipped_at"]
            # test that returned items were shipped and delivered first
            case OrderStatus.RETURNED:
                assert item["shipped_at"] is not None
                assert item["delivered_at"] is not None
                assert item["delivered_at"] >= item["shipped_at"]
            # test that shipped items have a shipping date but no delivery date
            case OrderStatus.SHIPPED:
                assert item["shipped_at"] is not None
                assert item["delivered_at"] is None
            # test that pending or cancelled items have no shipping or delivery dates
            case OrderStatus.PENDING | OrderStatus.CANCELLED:
                assert item["shipped_at"] is None
                assert item["delivered_at"] is None


def test_updated_at_is_after_created_at(rng, items):
    for item in items:
        assert item["created_at"] is not None
        assert item["updated_at"] is not None
        assert item["updated_at"] >= item["created_at"]


def test_updated_at_is_not_before_last_event(items):
    for item in items:
        last_event = item["delivered_at"] or item["shipped_at"] or item["created_at"]
        assert item["updated_at"] >= last_event


def test_reproducibility(rng, date_start, date_end):
    seed = 12345
    rng.seed(seed)
    items1 = build_order_items(500, rng, date_start, date_end)
    rng.seed(seed)
    items2 = build_order_items(500, rng, date_start, date_end)
    assert items1 == items2
