"""Orders and their items, with timestamps and statuses that follow a realistic lifecycle."""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from dataforge.domain.enums import OrderStatus
from dataforge.domain.order_item_row import OrderItemRow
from dataforge.ids import new_uuid7

Row = dict[str, object]

CANCEL_RATE = 0.03
RETURN_RATE = 0.04
# How many items an order has, and how often (weights, not percentages).
ITEM_COUNTS = [1, 2, 3, 4, 5]
ITEM_COUNT_WEIGHTS = [35, 30, 18, 10, 7]
# How many units of one item are bought, and how often.
QUANTITIES = [1, 2, 3, 5, 10]
QUANTITY_WEIGHTS = [70, 15, 8, 5, 2]


@dataclass(frozen=True)
class StockedOffer:
    inventory_id: UUID
    price: Decimal
    discount_pct: int


@dataclass(frozen=True)
class OrderSources:
    """What an order can point to. Built by the generator or read back from Postgres."""

    customer_ids: list[UUID]
    shipping_provider_ids: list[UUID]
    stock: list[StockedOffer]


@dataclass(frozen=True)
class Lifecycle:
    status: OrderStatus
    shipped_at: datetime | None
    delivered_at: datetime | None
    updated_at: datetime


def build_orders(
    rand_gen: random.Random,
    sources: OrderSources,
    order_count: int,
    start: datetime,
    end: datetime,
) -> tuple[list[Row], list[OrderItemRow]]:
    """Orders created between start and end, in time order, with their state as of `end`."""
    span_seconds = int((end - start).total_seconds())
    created_times = sorted(
        start + timedelta(seconds=rand_gen.randint(0, span_seconds)) for _ in range(order_count)
    )
    orders: list[Row] = []
    items: list[OrderItemRow] = []
    for created_at in created_times:
        order_id = new_uuid7(rand_gen, created_at)
        orders.append(
            {
                "id": order_id,
                "customer_id": rand_gen.choice(sources.customer_ids),
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
        items.extend(_build_items(rand_gen, sources, order_id, created_at, end))
    return orders, items


def _build_items(
    rand_gen: random.Random,
    sources: OrderSources,
    order_id: UUID,
    created_at: datetime,
    now: datetime,
) -> list[OrderItemRow]:
    # One shipment per order, so all its items ship and arrive together. Returns happen per item.
    lifecycle = order_lifecycle(rand_gen, created_at, now)
    shipping_provider_id = rand_gen.choice(sources.shipping_provider_ids)
    item_count = rand_gen.choices(ITEM_COUNTS, weights=ITEM_COUNT_WEIGHTS)[0]
    items: list[OrderItemRow] = []
    for offer in rand_gen.sample(sources.stock, k=min(item_count, len(sources.stock))):
        item_lifecycle = _maybe_returned(rand_gen, lifecycle, now)
        items.append(
            {
                "id": new_uuid7(rand_gen, created_at),
                "order_id": order_id,
                "inventory_id": offer.inventory_id,
                "shipping_provider_id": shipping_provider_id,
                "price_at_the_time": offer.price,
                "discount_pct_at_the_time": offer.discount_pct,
                "order_status": item_lifecycle.status,
                "quantity": rand_gen.choices(QUANTITIES, weights=QUANTITY_WEIGHTS)[0],
                "shipped_at": item_lifecycle.shipped_at,
                "delivered_at": item_lifecycle.delivered_at,
                "created_at": created_at,
                "updated_at": item_lifecycle.updated_at,
            }
        )
    return items


def order_lifecycle(rand_gen: random.Random, created_at: datetime, now: datetime) -> Lifecycle:
    """Where an order created at `created_at` stands at `now`."""
    pending = Lifecycle(OrderStatus.PENDING, None, None, created_at)
    if rand_gen.random() < CANCEL_RATE:
        cancelled_at = created_at + _between(rand_gen, timedelta(minutes=5), timedelta(days=1))
        if cancelled_at > now:
            return pending
        return Lifecycle(OrderStatus.CANCELLED, None, None, cancelled_at)
    shipped_at = created_at + _between(rand_gen, timedelta(hours=4), timedelta(days=3))
    if shipped_at > now:
        return pending
    delivered_at = shipped_at + _between(rand_gen, timedelta(days=1), timedelta(days=7))
    if delivered_at > now:
        return Lifecycle(OrderStatus.SHIPPED, shipped_at, None, shipped_at)
    return Lifecycle(OrderStatus.DELIVERED, shipped_at, delivered_at, delivered_at)


def _maybe_returned(rand_gen: random.Random, lifecycle: Lifecycle, now: datetime) -> Lifecycle:
    if lifecycle.status is not OrderStatus.DELIVERED or rand_gen.random() >= RETURN_RATE:
        return lifecycle
    returned_at = lifecycle.updated_at + _between(rand_gen, timedelta(days=1), timedelta(days=14))
    if returned_at > now:
        return lifecycle
    return Lifecycle(
        OrderStatus.RETURNED, lifecycle.shipped_at, lifecycle.delivered_at, returned_at
    )


def _between(rand_gen: random.Random, low: timedelta, high: timedelta) -> timedelta:
    return timedelta(seconds=rand_gen.randint(int(low.total_seconds()), int(high.total_seconds())))
