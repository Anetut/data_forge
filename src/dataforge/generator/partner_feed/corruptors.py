"""Functions that damage a clean row, to simulate the problems validation must reject."""

import random
from datetime import datetime
from uuid import UUID

from dataforge.generator.partner_feed.lines import RawRow

# A sample of the required fields, enough to exercise the missing-value check.
REQUIRED_FIELDS = ["price_at_the_time", "order_status", "quantity", "created_at", "inventory_id"]


def missing(rand_gen: random.Random, row: RawRow) -> str:
    field = rand_gen.choice(REQUIRED_FIELDS)
    if rand_gen.random() < 0.5:
        del row[field]
        return f"{field} absent"
    row[field] = None
    return f"{field} is null"


def invalid(rand_gen: random.Random, row: RawRow) -> str:
    choice = rand_gen.randrange(5)
    if choice == 0:
        row["quantity"] = rand_gen.choice([0, -1, -3])
        return f"quantity {row['quantity']}"
    if choice == 1:
        row["discount_pct_at_the_time"] = 120
        return "discount_pct 120"
    if choice == 2:
        row["order_status"] = "Shiped"
        return "unknown status 'Shiped'"
    if choice == 3:
        row["price_at_the_time"] = "-15.00"
        return "negative price"
    row["delivered_at"] = row["created_at"]
    row["shipped_at"] = None
    return "delivered without being shipped"


def bad_format(rand_gen: random.Random, row: RawRow) -> str:
    choice = rand_gen.randrange(5)
    created_at = datetime.fromisoformat(str(row["created_at"]))
    if choice == 0:
        row["created_at"] = created_at.strftime("%Y-%m-%d %H:%M:%S")
        return "created_at without UTC offset"
    if choice == 1:
        row["created_at"] = created_at.strftime("%d/%m/%Y %H:%M")
        return "created_at as dd/mm/yyyy"
    if choice == 2:
        row["price_at_the_time"] = float(str(row["price_at_the_time"]))
        return "price as JSON number"
    if choice == 3:
        row["price_at_the_time"] = str(row["price_at_the_time"]).replace(".", ",")
        return "price with decimal comma"
    row["quantity"] = str(row["quantity"])
    return "quantity as string"


def orphan(rand_gen: random.Random, row: RawRow) -> str:
    row["inventory_id"] = str(UUID(int=rand_gen.getrandbits(128), version=4))
    return "inventory_id not in our inventory"
