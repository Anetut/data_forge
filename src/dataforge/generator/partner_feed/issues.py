"""Injects data quality problems into feed lines on purpose, so validation can be tested."""

import dataclasses
import random
from datetime import timedelta
from typing import assert_never

from dataforge.domain.enums import OrderStatus
from dataforge.domain.order_item_row import OrderItemRow
from dataforge.generator.partner_feed.corruptors import bad_format, invalid, missing, orphan
from dataforge.generator.partner_feed.lines import FeedLine, Issue
from dataforge.ids import new_uuid7

DEFAULT_ISSUE_RATE = 0.08  # 8% of lines, unless the caller asks for a different rate

CORRUPTORS = {
    Issue.MISSING_VALUE: missing,
    Issue.INVALID_VALUE: invalid,
    Issue.BAD_FORMAT: bad_format,
    Issue.ORPHAN_REFERENCE: orphan,
}

IssueLines = tuple[FeedLine, FeedLine | None]
"""(line emitted now, line re-sent later in the feed or None)."""


def insert_random_issues_to_items(
    rand_gen: random.Random, items: list[OrderItemRow], issue_rate: float
) -> list[FeedLine]:
    """One feed line per item. About `issue_rate` of them (0.08 is 8%) get an injected problem."""
    lines: list[FeedLine] = []
    resent: list[tuple[int, FeedLine]] = []  # (earliest position, line)
    for item in items:
        if not has_issue(rand_gen, issue_rate):
            lines.append(FeedLine.from_item(item))
            continue
        line_now, line_later = _issue_lines(rand_gen, item, pick_random_issue(rand_gen))
        lines.append(line_now)
        if line_later is not None:
            resent.append((len(lines), line_later))

    # Re-sent rows end up somewhere after the original, not necessarily right next to it.
    for earliest_position, line in reversed(resent):
        lines.insert(rand_gen.randint(earliest_position, len(lines)), line)

    return lines


def has_issue(rand_gen: random.Random, issue_rate: float = DEFAULT_ISSUE_RATE) -> bool:
    return rand_gen.random() < issue_rate


def pick_random_issue(rand_gen: random.Random) -> Issue:
    return rand_gen.choice(list(Issue))


def _issue_lines(rand_gen: random.Random, item: OrderItemRow, issue: Issue) -> IssueLines:
    match issue:
        case Issue.DUPLICATE:
            return make_duplicate(item)
        case Issue.UPDATE:
            return make_update(item)
        case Issue.LATE_ARRIVAL:
            return make_late_arrival(rand_gen, item)
        case Issue.MISSING_VALUE | Issue.INVALID_VALUE | Issue.BAD_FORMAT | Issue.ORPHAN_REFERENCE:
            return make_corrupted(rand_gen, item, issue)
        case _:
            # Pyright reports an error here when a new Issue member is not handled above.
            assert_never(issue)


def make_duplicate(item: OrderItemRow) -> IssueLines:
    """The partner sends the same line again, unchanged, somewhere later in the file."""
    return FeedLine.from_item(item), FeedLine.from_item(
        item, Issue.DUPLICATE, "exact copy of an earlier line"
    )


def make_update(item: OrderItemRow) -> IssueLines:
    """The partner sends the item again later, with its next status and a newer updated_at."""
    updated, detail = _progressed(item)
    return FeedLine.from_item(item), FeedLine.from_item(updated, Issue.UPDATE, detail)


def make_late_arrival(rand_gen: random.Random, item: OrderItemRow) -> IssueLines:
    """The item happened days ago and only arrives in this batch."""
    late, detail = _shifted_back(rand_gen, item)
    return FeedLine.from_item(late, Issue.LATE_ARRIVAL, detail), None


def make_corrupted(rand_gen: random.Random, item: OrderItemRow, issue: Issue) -> IssueLines:
    """A row damaged so that validation must reject it."""
    line = FeedLine.from_item(item)
    detail = CORRUPTORS[issue](rand_gen, line.row)  # This changes line.row in place.
    return dataclasses.replace(line, issue=issue, detail=detail), None


def _progressed(item: OrderItemRow) -> tuple[OrderItemRow, str]:
    """The same item six hours later, moved to its next status."""
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


def _shifted_back(rand_gen: random.Random, item: OrderItemRow) -> tuple[OrderItemRow, str]:
    """The same item 3 to 14 days earlier, with a new id that matches the earlier time."""
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
