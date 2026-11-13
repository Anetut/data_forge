"""Reference data: the people, catalogue and warehouses that orders point to."""

import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from dataforge.generator.orders import OrderSources, Row, StockedOffer
from dataforge.ids import new_uuid7

DISCOUNTS = [0, 0, 0, 0, 0, 0, 5, 10, 15, 20, 25, 50]


@dataclass(frozen=True)
class Volumes:
    managers: int = 10
    shipping_providers: int = 5
    customers: int = 2_000
    sellers: int = 50
    products: int = 1_000
    categories: int = 20
    warehouses: int = 5
    offers: int = 2_000


@dataclass(frozen=True)
class ReferenceData:
    tables: dict[str, list[Row]]  # insertion order respects the foreign keys
    sources: OrderSources


def build_reference(rand_gen: random.Random, volumes: Volumes, before: datetime) -> ReferenceData:
    """Reference rows, all created during the year before `before`."""

    def entity() -> tuple[UUID, Row]:
        created_at = before - timedelta(seconds=rand_gen.randint(0, 365 * 24 * 3600))
        entity_id = new_uuid7(rand_gen, created_at)
        return entity_id, {"id": entity_id, "created_at": created_at, "updated_at": created_at}

    tables: dict[str, list[Row]] = {name: [] for name in TABLE_ORDER}

    manager_ids = []
    for i in range(volumes.managers):
        manager_id, row = entity()
        hire_date = before.date() - timedelta(days=rand_gen.randint(400, 4000))
        row |= {
            "name": f"Manager {i}",
            "email": f"manager{i}@dataforge.test",
            "hire_date": hire_date,
        }
        tables["manager"].append(row)
        manager_ids.append(manager_id)

    shipping_provider_ids = []
    for i in range(volumes.shipping_providers):
        provider_id, row = entity()
        row |= {
            "manager_id": rand_gen.choice(manager_ids),
            "name": f"Carrier {i}",
            "cost_per_shipment": Decimal(rand_gen.randint(299, 1999)).scaleb(-2),
        }
        tables["shipping_provider"].append(row)
        shipping_provider_ids.append(provider_id)

    customer_ids = []
    for i in range(volumes.customers):
        customer_id, row = entity()
        favourite = rand_gen.choice(shipping_provider_ids) if rand_gen.random() < 0.3 else None
        row |= {
            "email": f"customer{i}@dataforge.test",
            "name": f"Customer {i}",
            "favourite_shipping_provider_id": favourite,
        }
        tables["customer"].append(row)
        customer_ids.append(customer_id)

    seller_ids = _named(tables["seller"], entity, "Seller", volumes.sellers)
    product_ids = _named(tables["product"], entity, "Product", volumes.products)
    category_ids = _named(tables["category"], entity, "Category", volumes.categories)
    for product_id in product_ids:
        for category_id in rand_gen.sample(category_ids, k=rand_gen.randint(1, 2)):
            tables["product_item_junction"].append(
                {
                    "id": new_uuid7(rand_gen, before),
                    "product_id": product_id,
                    "category_id": category_id,
                }
            )

    warehouse_ids = []
    for i in range(volumes.warehouses):
        warehouse_id, row = entity()
        row |= {
            "manager_id": rand_gen.choice(manager_ids),
            "name": f"Warehouse {i}",
            "capacity": rand_gen.randint(10_000, 100_000),
        }
        tables["warehouse"].append(row)
        warehouse_ids.append(warehouse_id)

    stock = []
    for _ in range(volumes.offers):
        offer_id, row = entity()
        price = Decimal(rand_gen.randint(199, 49_999)).scaleb(-2)
        discount_pct = rand_gen.choice(DISCOUNTS)
        row |= {
            "seller_id": rand_gen.choice(seller_ids),
            "product_id": rand_gen.choice(product_ids),
            "price": price,
            "discount_pct": discount_pct,
        }
        tables["offer"].append(row)
        # Each offer is stocked in one or two warehouses; (warehouse, offer) is unique.
        warehouse_count = min(rand_gen.randint(1, 2), len(warehouse_ids))
        for warehouse_id in rand_gen.sample(warehouse_ids, k=warehouse_count):
            inventory_id, row = entity()
            row |= {
                "warehouse_id": warehouse_id,
                "offer_id": offer_id,
                "stock": rand_gen.randint(0, 500),
            }
            tables["inventory"].append(row)
            stock.append(StockedOffer(inventory_id, price, discount_pct))

    return ReferenceData(tables, OrderSources(customer_ids, shipping_provider_ids, stock))


TABLE_ORDER = [
    "manager",
    "shipping_provider",
    "customer",
    "seller",
    "product",
    "category",
    "product_item_junction",
    "warehouse",
    "offer",
    "inventory",
]


def _named(
    rows: list[Row], entity: Callable[[], tuple[UUID, Row]], label: str, count: int
) -> list[UUID]:
    ids = []
    for i in range(count):
        entity_id, row = entity()
        rows.append(row | {"name": f"{label} {i}"})
        ids.append(entity_id)
    return ids
