from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dataforge.ingestion import landing
from dataforge.ingestion.landing import write_landing_file

SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("price_at_the_time", pa.decimal128(10, 2)),
        ("quantity", pa.int32()),
        ("shipped_at", pa.timestamp("us", tz="UTC")),
        ("updated_at", pa.timestamp("us", tz="UTC")),
    ]
)
ROWS: list[dict[str, object]] = [
    {
        "id": UUID("0194a7c1-8c2e-7b3a-9f10-2d5e6a7b8c9d"),
        "price_at_the_time": Decimal("10.50"),
        "quantity": 2,
        "shipped_at": None,
        "updated_at": datetime(2026, 11, 16, 9, 30, tzinfo=UTC),
    },
    {
        "id": UUID("0194a7c1-8c2e-7b3a-9f10-2d5e6a7b8c9e"),
        "price_at_the_time": Decimal("199.99"),
        "quantity": 1,
        "shipped_at": datetime(2026, 11, 16, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 11, 16, 10, 0, tzinfo=UTC),
    },
]


def test_file_lands_in_table_folder_named_by_batch(tmp_path):
    path = write_landing_file(
        tmp_path, "order_item", "20261116T093000Z", datetime.now(UTC), ROWS, SCHEMA
    )
    assert path == tmp_path / "order_item" / "20261116T093000Z.parquet"
    assert path.exists()


def test_file_has_the_given_schema_with_metadata(tmp_path):
    path = write_landing_file(tmp_path, "order_item", "b1", datetime.now(UTC), ROWS, SCHEMA)
    expected = (
        SCHEMA.append(pa.field("_batch_id", pa.string()))
        .append(pa.field("_extracted_at", pa.timestamp("us", tz="UTC")))
        .append(pa.field("_source", pa.string()))
    )
    assert pq.read_schema(path).equals(expected)


def test_every_row_carries_metadata(tmp_path):
    extracted_at = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    path = write_landing_file(tmp_path, "order_item", "b1", extracted_at, ROWS, SCHEMA)
    for row in pq.read_table(path).to_pylist():
        assert row["_batch_id"] == "b1"
        assert row["_extracted_at"] == extracted_at
        assert row["_source"] == "postgres.order_item"


def test_all_rows_are_written(tmp_path):
    path = write_landing_file(tmp_path, "order_item", "b1", datetime.now(UTC), ROWS, SCHEMA)
    assert pq.read_table(path).num_rows == len(ROWS)


def test_values_round_trip_with_their_types(tmp_path):
    path = write_landing_file(tmp_path, "order_item", "b1", datetime.now(UTC), ROWS, SCHEMA)
    [first, second] = pq.read_table(path).to_pylist()
    assert first["id"] == "0194a7c1-8c2e-7b3a-9f10-2d5e6a7b8c9d"  # UUID stored as string
    assert first["price_at_the_time"] == Decimal("10.50")
    assert first["shipped_at"] is None
    assert second["shipped_at"] == datetime(2026, 11, 16, 10, 0, tzinfo=UTC)


def test_input_rows_are_not_modified(tmp_path):
    rows = [dict(row) for row in ROWS]
    write_landing_file(tmp_path, "order_item", "b1", datetime.now(UTC), rows, SCHEMA)
    assert rows == ROWS
    assert type(rows[0]["id"]) is UUID


def test_rows_not_matching_the_schema_are_rejected(tmp_path):
    bad = [ROWS[0] | {"quantity": "two"}]
    with pytest.raises((pa.ArrowInvalid, pa.ArrowTypeError)):
        write_landing_file(tmp_path, "order_item", "b1", datetime.now(UTC), bad, SCHEMA)


def test_crash_during_write_leaves_no_landing_file(tmp_path, monkeypatch):
    def crash_halfway(table, where, *args, **kwargs):
        with open(where, "wb") as file:
            file.write(b"PAR1 half a file")  # a truncated Parquet file
        raise OSError("disk full")

    monkeypatch.setattr(landing.pq, "write_table", crash_halfway)
    with pytest.raises(OSError):
        write_landing_file(tmp_path, "order_item", "b1", datetime.now(UTC), ROWS, SCHEMA)
    assert list((tmp_path / "order_item").glob("*.parquet")) == []
