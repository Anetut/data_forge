import json
import random
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest

from dataforge.domain.enums import OrderStatus
from dataforge.file_formats.jsonl_file import parse_jsonl_row
from dataforge.generator.feed import Issue, build_feed, write_feed
from dataforge.generator.orders import build_orders
from dataforge.generator.reference import ReferenceData, Volumes, build_reference

NOW = datetime(2026, 6, 1, tzinfo=UTC)
START = NOW - timedelta(days=365)
SMALL = Volumes(customers=50, sellers=5, products=40, categories=5, offers=60)


@pytest.fixture
def reference() -> ReferenceData:
    return build_reference(random.Random(31), SMALL, before=START)


@pytest.fixture
def orders_and_items(reference):
    return build_orders(random.Random(31), reference.sources, 2_000, START, NOW)


def test_reference_unique_constraints_hold(reference):
    emails = [row["email"] for row in reference.tables["customer"]]
    assert len(emails) == len(set(emails))
    pairs = [(row["warehouse_id"], row["offer_id"]) for row in reference.tables["inventory"]]
    assert len(pairs) == len(set(pairs))


def test_reference_foreign_keys_point_to_existing_rows(reference):
    offer_ids = {row["id"] for row in reference.tables["offer"]}
    assert {row["offer_id"] for row in reference.tables["inventory"]} <= offer_ids
    inventory_ids = {row["id"] for row in reference.tables["inventory"]}
    assert {offer.inventory_id for offer in reference.sources.stock} == inventory_ids


def test_items_belong_to_generated_orders_and_stock(reference, orders_and_items):
    orders, items = orders_and_items
    order_ids = {order["id"] for order in orders}
    stock_ids = {offer.inventory_id for offer in reference.sources.stock}
    assert {item["order_id"] for item in items} == order_ids
    assert {item["inventory_id"] for item in items} <= stock_ids


def test_orders_repeat_across_items(orders_and_items):
    orders, items = orders_and_items
    assert len(items) > len(orders)


def test_orders_and_ids_are_in_time_order(orders_and_items):
    orders, _ = orders_and_items
    assert [order["created_at"] for order in orders] == sorted(o["created_at"] for o in orders)
    assert [order["id"] for order in orders] == sorted(order["id"] for order in orders)


def test_item_timestamps_follow_the_lifecycle(orders_and_items):
    _, items = orders_and_items
    for item in items:
        last_event = item["delivered_at"] or item["shipped_at"] or item["created_at"]
        assert item["created_at"] <= last_event <= item["updated_at"] <= NOW
        if item["delivered_at"] is not None:
            assert item["shipped_at"] is not None
            assert item["delivered_at"] >= item["shipped_at"]


def test_item_status_matches_timestamps(orders_and_items):
    _, items = orders_and_items
    for item in items:
        match item["order_status"]:
            case OrderStatus.PENDING | OrderStatus.CANCELLED:
                assert item["shipped_at"] is None and item["delivered_at"] is None
            case OrderStatus.SHIPPED:
                assert item["shipped_at"] is not None and item["delivered_at"] is None
            case OrderStatus.DELIVERED | OrderStatus.RETURNED:
                assert item["delivered_at"] is not None


def test_old_orders_are_finished_and_recent_ones_are_not(orders_and_items):
    _, items = orders_and_items
    old = Counter(i["order_status"] for i in items if i["created_at"] < NOW - timedelta(days=30))
    assert old[OrderStatus.PENDING] == 0 and old[OrderStatus.SHIPPED] == 0
    recent = Counter(i["order_status"] for i in items if i["created_at"] > NOW - timedelta(hours=2))
    assert recent[OrderStatus.DELIVERED] == 0


def test_generation_is_reproducible(reference):
    first = build_orders(random.Random(5), reference.sources, 100, START, NOW)
    second = build_orders(random.Random(5), reference.sources, 100, START, NOW)
    assert first == second


@pytest.fixture
def feed(reference):
    return build_feed(random.Random(31), reference.sources, 3_000, NOW, issue_rate=0.2)


def test_feed_manifest_points_at_the_right_lines(feed):
    rows, manifest = feed
    for entry in manifest:
        assert rows[entry["line"] - 1].get("id") == entry["id"]


def test_feed_injects_every_issue_type(feed):
    _, manifest = feed
    assert {entry["issue"] for entry in manifest} == {issue.value for issue in Issue}


def test_feed_rows_without_issues_parse_cleanly(feed):
    rows, manifest = feed
    flagged = {entry["line"] for entry in manifest}
    for line, row in enumerate(rows, start=1):
        if line not in flagged:
            parse_jsonl_row(row)


@pytest.mark.parametrize("issue", [Issue.MISSING_VALUE, Issue.BAD_FORMAT])
def test_feed_structural_issues_fail_parsing(feed, issue):
    rows, manifest = feed
    for entry in manifest:
        if entry["issue"] == issue:
            with pytest.raises((KeyError, TypeError, ValueError, ArithmeticError)):
                parse_jsonl_row(rows[entry["line"] - 1])


def test_feed_duplicates_and_updates_come_after_the_original(feed):
    rows, manifest = feed
    for entry in manifest:
        if entry["issue"] in (Issue.DUPLICATE, Issue.UPDATE):
            first_line = next(n for n, row in enumerate(rows, 1) if row.get("id") == entry["id"])
            assert first_line < entry["line"]


def test_write_feed_creates_feed_and_manifest(tmp_path, feed):
    rows, manifest = feed
    path = write_feed(tmp_path, NOW, rows, manifest)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == rows
    written = json.loads(path.with_name(path.stem + ".manifest.json").read_text(encoding="utf-8"))
    assert written["issues"] == manifest
