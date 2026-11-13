"""A partner's order-item feed in JSON Lines, with data quality problems injected on purpose.

The partner sells our stock: `inventory_id` and `shipping_provider_id` must exist in our
database, `order_id` is the partner's own and never does. A manifest lists every injected
problem by line, so validation can be checked against it.
"""

import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from dataforge.domain.enums import OrderStatus
from dataforge.domain.order_item_row import OrderItemRow
from dataforge.generator.orders import OrderSources, build_orders
from dataforge.ids import new_uuid7

RawRow = dict[str, object]


class Issue(StrEnum):
    # The row breaks a rule; validation must reject it.
    MISSING_VALUE = "missing_value"
    INVALID_VALUE = "invalid_value"
    BAD_FORMAT = "bad_format"
    ORPHAN_REFERENCE = "orphan_reference"
    # The row is valid; later layers must handle it.
    DUPLICATE = "duplicate"
    LATE_ARRIVAL = "late_arrival"
    UPDATE = "update"


REQUIRED_FIELDS = ["price_at_the_time", "order_status", "quantity", "created_at", "inventory_id"]


def build_feed(
    rand_gen: random.Random,
    sources: OrderSources,
    row_count: int,
    batch_time: datetime,
    issue_rate: float,
) -> tuple[list[RawRow], list[dict[str, object]]]:
    """Feed rows as parsed JSON (before any validation) and the manifest of injected issues."""
    # Generate orders until there are enough items, then cut to size.
    _, items = build_orders(
        rand_gen, sources, row_count, batch_time - timedelta(days=1), batch_time
    )
    items = items[:row_count]

    rows: list[RawRow] = []
    issues: dict[int, tuple[Issue, str]] = {}  # keyed by id() of the emitted row
    extras: list[tuple[int, RawRow, Issue, str]] = []  # (earliest position, row, issue, detail)
    for item in items:
        if rand_gen.random() >= issue_rate:
            rows.append(to_raw(item))
            continue
        issue = rand_gen.choice(list(Issue))
        if issue is Issue.DUPLICATE:
            row = to_raw(item)
            rows.append(row)
            extras.append((len(rows), dict(row), issue, "exact copy of an earlier line"))
        elif issue is Issue.UPDATE:
            rows.append(to_raw(item))
            updated, detail = _progressed(item)
            extras.append((len(rows), to_raw(updated), issue, detail))
        elif issue is Issue.LATE_ARRIVAL:
            late, detail = _late(rand_gen, item)
            row = to_raw(late)
            rows.append(row)
            issues[id(row)] = (issue, detail)
        else:
            row = to_raw(item)
            detail = CORRUPTORS[issue](rand_gen, row)
            rows.append(row)
            issues[id(row)] = (issue, detail)

    # Re-sent rows land somewhere after the original, not necessarily next to it.
    # Back to front, so an insert never shifts an original that is still to be used.
    for earliest, row, issue, detail in reversed(extras):
        rows.insert(rand_gen.randint(earliest, len(rows)), row)
        issues[id(row)] = (issue, detail)

    manifest = [
        {
            "line": line,
            "id": row.get("id"),
            "issue": issues[id(row)][0].value,
            "detail": issues[id(row)][1],
        }
        for line, row in enumerate(rows, start=1)
        if id(row) in issues
    ]
    return rows, manifest


def write_feed(
    directory: Path, batch_time: datetime, rows: list[RawRow], manifest: list[dict[str, object]]
) -> Path:
    """Write `<batch>.jsonl` and `<batch>.manifest.json`; return the feed path."""
    directory.mkdir(parents=True, exist_ok=True)
    name = f"partner_order_items_{batch_time:%Y%m%dT%H%M%SZ}"
    feed_path = directory / f"{name}.jsonl"
    with open(feed_path, "w", newline="", encoding="utf-8") as feed_file:
        for row in rows:
            feed_file.write(json.dumps(row) + "\n")
    summary = {"batch_time": batch_time.isoformat(), "rows": len(rows), "issues": manifest}
    (directory / f"{name}.manifest.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return feed_path


def to_raw(item: OrderItemRow) -> RawRow:
    """The JSON shape the partner sends: strings for IDs, decimals and timestamps."""
    return {key: _raw_value(value) for key, value in item.items()}


def _raw_value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _progressed(item: OrderItemRow) -> tuple[OrderItemRow, str]:
    """The same item re-sent later with its next status."""
    later = item["updated_at"] + timedelta(hours=6)
    updated = item.copy()
    updated["updated_at"] = later
    match item["order_status"]:
        case OrderStatus.PENDING:
            updated["order_status"] = OrderStatus.SHIPPED
            updated["shipped_at"] = later
        case OrderStatus.SHIPPED:
            updated["order_status"] = OrderStatus.DELIVERED
            updated["delivered_at"] = later
        case OrderStatus.DELIVERED:
            updated["order_status"] = OrderStatus.RETURNED
    return updated, f"{item['order_status']} -> {updated['order_status']}, newer updated_at"


def _late(rand_gen: random.Random, item: OrderItemRow) -> tuple[OrderItemRow, str]:
    """The item happened days ago and only arrives in this batch."""
    days = rand_gen.randint(3, 14)
    shift = timedelta(days=days)
    late: OrderItemRow = {
        **item,
        "created_at": item["created_at"] - shift,
        "updated_at": item["updated_at"] - shift,
        "shipped_at": item["shipped_at"] - shift if item["shipped_at"] else None,
        "delivered_at": item["delivered_at"] - shift if item["delivered_at"] else None,
    }
    late["id"] = new_uuid7(rand_gen, late["created_at"])
    return late, f"created {days} days before the batch"


def _missing(rand_gen: random.Random, row: RawRow) -> str:
    field = rand_gen.choice(REQUIRED_FIELDS)
    if rand_gen.random() < 0.5:
        del row[field]
        return f"{field} absent"
    row[field] = None
    return f"{field} is null"


def _invalid(rand_gen: random.Random, row: RawRow) -> str:
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


def _bad_format(rand_gen: random.Random, row: RawRow) -> str:
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


def _orphan(rand_gen: random.Random, row: RawRow) -> str:
    row["inventory_id"] = str(UUID(int=rand_gen.getrandbits(128), version=4))
    return "inventory_id not in our inventory"


CORRUPTORS = {
    Issue.MISSING_VALUE: _missing,
    Issue.INVALID_VALUE: _invalid,
    Issue.BAD_FORMAT: _bad_format,
    Issue.ORPHAN_REFERENCE: _orphan,
}
