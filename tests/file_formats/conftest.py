import random
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from dataforge.domain.enums import OrderStatus
from dataforge.domain.order_item_row import OrderItemRow
from dataforge.generator.data.orders import build_orders
from dataforge.generator.data.reference import Volumes, build_reference


@pytest.fixture
def items() -> list[OrderItemRow]:
    """500 generated order items, the same on every run."""
    rand_gen = random.Random(31)
    date_start = datetime(2020, 1, 1, tzinfo=UTC)
    date_end = datetime(2026, 1, 1, tzinfo=UTC)
    reference = build_reference(
        rand_gen, Volumes(customers=50, products=50, offers=100), date_start
    )
    _, order_items = build_orders(rand_gen, reference.sources, 500, date_start, date_end)
    return order_items[:500]


@pytest.fixture
def one_order_item_list() -> list[OrderItemRow]:
    return [
        {
            "id": UUID("240f16a7-6490-4d4a-8393-fd0e1cc62be5"),
            "order_id": UUID("b12f16a7-6490-4d4a-8393-fd0e1cc62be5"),
            "inventory_id": UUID("c12b65d7-d234-ca35-aa72-c12b65d7aa72"),
            "shipping_provider_id": UUID("d12c65d7-d234-cb35-a132-0c82a8d72d76"),
            "price_at_the_time": Decimal("100.15"),
            "discount_pct_at_the_time": 0,
            "order_status": OrderStatus.SHIPPED,
            "quantity": 1,
            "shipped_at": datetime.fromisoformat("2024-01-02T00:00:00Z"),
            "delivered_at": None,
            "created_at": datetime.fromisoformat("2024-01-01T00:00:00Z"),
            "updated_at": datetime.fromisoformat("2024-01-02T00:00:00Z"),
        }
    ]


@pytest.fixture
def raw_csv_row() -> dict[str, str]:
    return {
        "id": "240f16a7-6490-4d4a-8393-fd0e1cc62be5",
        "order_id": "b12f16a7-6490-4d4a-8393-fd0e1cc62be5",
        "inventory_id": "c12b65d7-d234-ca35-aa72-c12b65d7aa72",
        "shipping_provider_id": "d12c65d7-d234-cb35-a132-0c82a8d72d76",
        "price_at_the_time": "100.15",
        "discount_pct_at_the_time": "10",
        "order_status": "Shipped",
        "quantity": "1",
        "shipped_at": "2024-01-02 00:00:00+00:00",
        "delivered_at": "2024-02-02 00:00:00+00:00",
        "created_at": "2024-01-01 00:00:00+00:00",
        "updated_at": "2024-02-02 00:00:00+00:00",
    }


@pytest.fixture
def raw_jsonl_row() -> dict[str, object]:
    return {
        "id": "240f16a7-6490-4d4a-8393-fd0e1cc62be5",
        "order_id": "b12f16a7-6490-4d4a-8393-fd0e1cc62be5",
        "inventory_id": "c12b65d7-d234-ca35-aa72-c12b65d7aa72",
        "shipping_provider_id": "d12c65d7-d234-cb35-a132-0c82a8d72d76",
        "price_at_the_time": "100.15",
        "discount_pct_at_the_time": 10,
        "order_status": "Shipped",
        "quantity": 1,
        "shipped_at": "2024-01-02T00:00:00+00:00",
        "delivered_at": "2024-02-02T00:00:00+00:00",
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-02-02T00:00:00+00:00",
    }
