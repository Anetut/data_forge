"""Reference data: the people, catalogue and warehouses that orders point to.

Each table has its own small builder. The builders run in foreign-key order, because a row
can only point to rows that already exist (an offer needs a seller and a product, and so on).
"""

import random
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID

from dataforge.generator.data.orders import OrderSources, Row, StockedOffer
from dataforge.ids import new_uuid7

DISCOUNTS = [0, 0, 0, 0, 0, 0, 5, 10, 15, 20, 25, 50]
ONE_YEAR_SECONDS = 365 * 24 * 3600


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

    def scaled(self, factor: float) -> "Volumes":
        """The same shop `factor` times bigger: more customers, sellers, products and offers.

        Managers, carriers, categories and warehouses stay as they are: a bigger shop sells
        more things to more people, and it doesn't need ten times the warehouses.
        """
        return replace(
            self,
            customers=_at_least_one(self.customers * factor),
            sellers=_at_least_one(self.sellers * factor),
            products=_at_least_one(self.products * factor),
            offers=_at_least_one(self.offers * factor),
        )


@dataclass(frozen=True)
class ReferenceData:
    tables: dict[str, list[Row]]  # in insertion order, which follows the foreign keys
    sources: OrderSources


@dataclass(frozen=True)
class _EntityMaker:
    """Starts every reference row: a UUIDv7 id and a creation time in the year before `before`."""

    rand_gen: random.Random
    before: datetime

    def new(self) -> Row:
        created_at = self.before - timedelta(seconds=self.rand_gen.randint(0, ONE_YEAR_SECONDS))
        entity_id = new_uuid7(self.rand_gen, created_at)
        return {"id": entity_id, "created_at": created_at, "updated_at": created_at}


def build_reference(rand_gen: random.Random, volumes: Volumes, before: datetime) -> ReferenceData:
    """Reference rows, all created during the year before `before`."""
    # The order of these calls is the order of random draws: changing it changes the data.
    maker = _EntityMaker(rand_gen, before)
    managers = _managers(maker, volumes.managers)
    shipping_providers = _shipping_providers(maker, volumes.shipping_providers, _ids(managers))
    customers = _customers(maker, volumes.customers, _ids(shipping_providers))
    sellers = _named(maker, "Seller", volumes.sellers)
    products = _named(maker, "Product", volumes.products)
    categories = _named(maker, "Category", volumes.categories)
    product_categories = _product_categories(maker, _ids(products), _ids(categories))
    warehouses = _warehouses(maker, volumes.warehouses, _ids(managers))
    offers, inventory, stock = _offers_and_inventory(
        maker, volumes.offers, _ids(sellers), _ids(products), _ids(warehouses)
    )

    tables = {
        "manager": managers,
        "shipping_provider": shipping_providers,
        "customer": customers,
        "seller": sellers,
        "product": products,
        "category": categories,
        "product_item_junction": product_categories,
        "warehouse": warehouses,
        "offer": offers,
        "inventory": inventory,
    }
    sources = OrderSources(_ids(customers), _ids(shipping_providers), stock)
    return ReferenceData(tables, sources)


def _managers(maker: _EntityMaker, count: int) -> list[Row]:
    rows = []
    for i in range(count):
        row = maker.new()
        hire_date = maker.before.date() - timedelta(days=maker.rand_gen.randint(400, 4000))
        rows.append(
            row
            | {
                "name": f"Manager {i}",
                "email": f"manager{i}@dataforge.test",
                "hire_date": hire_date,
            }
        )
    return rows


def _shipping_providers(maker: _EntityMaker, count: int, manager_ids: list[UUID]) -> list[Row]:
    rows = []
    for i in range(count):
        row = maker.new()
        rows.append(
            row
            | {
                "manager_id": maker.rand_gen.choice(manager_ids),
                "name": f"Carrier {i}",
                "cost_per_shipment": _money(maker.rand_gen, 299, 1999),
            }
        )
    return rows


def _customers(maker: _EntityMaker, count: int, shipping_provider_ids: list[UUID]) -> list[Row]:
    rows = []
    for i in range(count):
        row = maker.new()
        # About 30% of customers have a favourite carrier.
        has_favourite = maker.rand_gen.random() < 0.3
        favourite = maker.rand_gen.choice(shipping_provider_ids) if has_favourite else None
        rows.append(
            row
            | {
                "email": f"customer{i}@dataforge.test",
                "name": f"Customer {i}",
                "favourite_shipping_provider_id": favourite,
            }
        )
    return rows


def _named(maker: _EntityMaker, label: str, count: int) -> list[Row]:
    """Rows that only have a name besides id and timestamps: sellers, products, categories."""
    return [maker.new() | {"name": f"{label} {i}"} for i in range(count)]


def _product_categories(
    maker: _EntityMaker, product_ids: list[UUID], category_ids: list[UUID]
) -> list[Row]:
    """Every product belongs to one or two categories."""
    rows = []
    for product_id in product_ids:
        category_count = maker.rand_gen.randint(1, 2)
        for category_id in maker.rand_gen.sample(category_ids, k=category_count):
            rows.append(
                {
                    "id": new_uuid7(maker.rand_gen, maker.before),
                    "product_id": product_id,
                    "category_id": category_id,
                }
            )
    return rows


def _warehouses(maker: _EntityMaker, count: int, manager_ids: list[UUID]) -> list[Row]:
    rows = []
    for i in range(count):
        row = maker.new()
        rows.append(
            row
            | {
                "manager_id": maker.rand_gen.choice(manager_ids),
                "name": f"Warehouse {i}",
                "capacity": maker.rand_gen.randint(10_000, 100_000),
            }
        )
    return rows


def _offers_and_inventory(
    maker: _EntityMaker,
    count: int,
    seller_ids: list[UUID],
    product_ids: list[UUID],
    warehouse_ids: list[UUID],
) -> tuple[list[Row], list[Row], list[StockedOffer]]:
    """Offers (a seller's price for a product), each stocked in one or two warehouses.

    Also returns the stock that orders can be placed against.
    """
    offers: list[Row] = []
    inventory: list[Row] = []
    stock: list[StockedOffer] = []
    for _ in range(count):
        offer = maker.new()
        price = _money(maker.rand_gen, 199, 49_999)
        discount_pct = maker.rand_gen.choice(DISCOUNTS)
        offers.append(
            offer
            | {
                "seller_id": maker.rand_gen.choice(seller_ids),
                "product_id": maker.rand_gen.choice(product_ids),
                "price": price,
                "discount_pct": discount_pct,
            }
        )
        # (warehouse, offer) is unique, so sample without repeats.
        warehouse_count = min(maker.rand_gen.randint(1, 2), len(warehouse_ids))
        for warehouse_id in maker.rand_gen.sample(warehouse_ids, k=warehouse_count):
            row = maker.new()
            inventory.append(
                row
                | {
                    "warehouse_id": warehouse_id,
                    "offer_id": offer["id"],
                    "stock": maker.rand_gen.randint(0, 500),
                }
            )
            stock.append(StockedOffer(_ids([row])[0], price, discount_pct))
    return offers, inventory, stock


def _money(rand_gen: random.Random, min_cents: int, max_cents: int) -> Decimal:
    """A price with exactly two decimals, between the given amounts in cents."""
    return Decimal(rand_gen.randint(min_cents, max_cents)).scaleb(-2)


def _ids(rows: list[Row]) -> list[UUID]:
    # Every reference row starts from `_EntityMaker.new`, which always sets a UUID id.
    return [cast(UUID, row["id"]) for row in rows]


def _at_least_one(count: float) -> int:
    # A small scale must never leave a table empty: orders need customers and stock.
    return max(1, round(count))
