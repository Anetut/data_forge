import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from dataforge.domain.enums import OrderStatus
from dataforge.domain.order_item_row import OrderItemRow


def build_order_items(
    count: int, rand_gen: random.Random, date_start: datetime, date_end: datetime
) -> list[OrderItemRow]:
    return [build_order_item(rand_gen, date_start, date_end) for _ in range(count)]


def build_order_item(
    rand_gen: random.Random, date_start: datetime, date_end: datetime
) -> OrderItemRow:
    rand_created_at: datetime = random_date(rand_gen, date_start, date_end)
    rand_order_status = rand_gen.choice(list(OrderStatus))
    shipped_at, delivered_at = get_random_order_shipping_details(
        rand_gen, rand_order_status, rand_created_at, date_end
    )
    order_item: OrderItemRow = {
        "id": random_uuid(rand_gen),
        "order_id": random_uuid(rand_gen),
        "inventory_id": random_uuid(rand_gen),
        "shipping_provider_id": random_uuid(rand_gen),
        "price_at_the_time": Decimal(rand_gen.randint(100, 9999999)).scaleb(-2),
        "discount_pct_at_the_time": rand_gen.randrange(0, 100, 5),
        "order_status": rand_order_status,
        "quantity": rand_gen.randint(1, 200),
        "shipped_at": shipped_at,
        "delivered_at": delivered_at,
        "created_at": rand_created_at,
        "updated_at": get_updated_at(rand_gen, rand_created_at, shipped_at, delivered_at, date_end),
    }
    return order_item


def get_random_order_shipping_details(
    rand_gen: random.Random, order_status: OrderStatus, created_at: datetime, end: datetime
) -> tuple[datetime | None, datetime | None]:
    # returns shipped_at, delivered_at
    match order_status:
        case OrderStatus.PENDING | OrderStatus.CANCELLED:
            return None, None
        case OrderStatus.SHIPPED:
            return random_date(rand_gen, created_at, end), None
        case OrderStatus.DELIVERED | OrderStatus.RETURNED:
            delivered_at: datetime = random_date(rand_gen, created_at, end)
            return random_date(rand_gen, created_at, delivered_at), delivered_at


def get_updated_at(
    rand_gen: random.Random,
    created_at: datetime,
    shipped_at: datetime | None,
    delivered_at: datetime | None,
    end: datetime,
) -> datetime:
    last_event = delivered_at or shipped_at or created_at
    return random_date(rand_gen, last_event, end)


def random_date(rand_gen: random.Random, start: datetime, end: datetime) -> datetime:
    span = int((end - start).total_seconds())  # seconds between start and end
    offset = rand_gen.randint(0, span)
    return start + timedelta(seconds=offset)


def random_uuid(rand_gen: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rand_gen.getrandbits(128), version=4)
