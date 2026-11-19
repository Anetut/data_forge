"""A partner's order-item feed in JSON Lines, with data quality problems injected on purpose.

The partner sells our stock: `inventory_id` and `shipping_provider_id` must exist in our
database, `order_id` is the partner's own and never does. A manifest lists every injected
problem by line, so validation can be checked against it.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from dataforge.generator.data.orders import OrderSources, build_orders
from dataforge.generator.partner_feed.issues import insert_random_issues_to_items
from dataforge.generator.partner_feed.lines import FeedLine, RawRow


def write_feed(
    directory: Path, batch_time: datetime, rows: list[RawRow], manifest: list[dict[str, object]]
) -> Path:
    """Write `<batch>.jsonl` and `<batch>.manifest.json`. Return the feed path."""
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

    lines: list[FeedLine] = insert_random_issues_to_items(rand_gen, items[:row_count], issue_rate)
    manifest = []
    raw_rows: list[RawRow] = []
    for index, feed_line in enumerate(lines, start=1):
        if feed_line.issue is not None:
            manifest.append(
                {
                    "line": index,
                    "id": feed_line.row.get("id"),
                    "issue": feed_line.issue.value,
                    "detail": feed_line.detail,
                }
            )
        raw_rows.append(feed_line.row)

    return raw_rows, manifest
