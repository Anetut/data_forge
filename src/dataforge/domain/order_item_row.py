"""One order_item row as typed Python values."""

from datetime import datetime
from decimal import Decimal
from typing import TypedDict
from uuid import UUID

from dataforge.domain.enums import OrderStatus


class OrderItemRow(TypedDict):
    id: UUID
    order_id: UUID
    inventory_id: UUID
    shipping_provider_id: UUID
    price_at_the_time: Decimal
    discount_pct_at_the_time: int
    order_status: OrderStatus
    quantity: int
    shipped_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime


ORDER_ITEM_COLUMNS = list(OrderItemRow.__annotations__)
