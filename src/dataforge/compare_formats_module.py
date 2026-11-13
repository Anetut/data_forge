"""Compare CSV, JSON Lines and Parquet using generated order items."""

import random
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import TypeVar

from pyarrow import parquet

from dataforge.domain.order_item_row import ORDER_ITEM_COLUMNS, OrderItemRow
from dataforge.file_formats.csv_file import parse_csv_row, read_csv, write_csv
from dataforge.file_formats.jsonl_file import parse_jsonl_row, read_jsonl, write_jsonl
from dataforge.file_formats.parquet_file import (
    parse_parquet_binary_id_row,
    parse_parquet_row,
    read_parquet,
    write_parquet,
    write_parquet_file_with_binary_id,
)
from dataforge.generator.orders import build_orders
from dataforge.generator.reference import Volumes, build_reference

SEED = 31
ROW_COUNT = 100_000
TIMING_RUNS = 3
# Assumes the src layout and an editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_OUTPUT_DIR = PROJECT_ROOT / "data"
T = TypeVar("T")


def main() -> None:
    print("Creating mock data...")
    random_generator = random.Random(SEED)
    date_start = datetime(2020, 1, 1, tzinfo=UTC)
    date_end = datetime(2026, 1, 1, tzinfo=UTC)
    reference = build_reference(random_generator, Volumes(), before=date_start)
    # About 2.2 items per order; cut to exactly ROW_COUNT so results stay comparable.
    _, items = build_orders(random_generator, reference.sources, ROW_COUNT, date_start, date_end)
    rows = items[:ROW_COUNT]
    run_csv_comparison(rows)
    run_json_comparison(rows)
    run_parquet_comparison(rows)
    run_parquet_with_binary_uuid_comparison(rows)
    run_pyarrow_to_read_comparison()


def run_csv_comparison(rows: list[OrderItemRow]) -> None:
    # CSV write and read performance test
    csv_file_path = DATA_OUTPUT_DIR / "order_items.csv"
    print("Testing performance for .csv files...: ")
    wrap_io_ops_in_time_measurements(csv_file_path, rows, write_csv, read_csv, parse_csv_row)


def run_json_comparison(rows: list[OrderItemRow]) -> None:
    # JSON Lines write and read performance test
    jsonl_file_path = DATA_OUTPUT_DIR / "order_items.jsonl"
    print("Testing performance for .jsonl files...: ")
    wrap_io_ops_in_time_measurements(
        jsonl_file_path, rows, write_jsonl, read_jsonl, parse_jsonl_row
    )


def run_parquet_comparison(rows: list[OrderItemRow]) -> None:
    # Parquet write and read performance test
    parquet_file_path = DATA_OUTPUT_DIR / "order_items.parquet"
    print("Testing performance for .parquet files...: ")
    wrap_io_ops_in_time_measurements(
        parquet_file_path, rows, write_parquet, read_parquet, parse_parquet_row
    )


def run_parquet_with_binary_uuid_comparison(rows: list[OrderItemRow]) -> None:
    # Parquet write and read performance test with uuids as binary
    parquet_file_path = DATA_OUTPUT_DIR / "order_items_binary_uuid.parquet"
    print("Testing performance for .parquet files with uuids converted as binary...: ")
    wrap_io_ops_in_time_measurements(
        parquet_file_path,
        rows,
        write_parquet_file_with_binary_id,
        read_parquet,
        parse_parquet_binary_id_row,
    )


def run_pyarrow_to_read_comparison() -> None:
    # Splits a Parquet read into reading the file and converting it to Python objects
    for name in ["order_items.parquet", "order_items_binary_uuid.parquet"]:
        measure_pyarrow_read(DATA_OUTPUT_DIR / name)


def measure_pyarrow_read(file_path: Path) -> None:
    table = parquet.read_table(file_path)
    _, file_seconds = _avg_of(lambda: parquet.read_table(file_path))
    _, python_seconds = _avg_of(lambda: table.to_pylist())
    print(
        f"{file_path.name}: file -> Arrow {file_seconds:.3f} s, "
        f"Arrow -> Python {python_seconds:.2f} s"
    )


def wrap_io_ops_in_time_measurements(
    file_path: Path,
    rows: list[OrderItemRow],
    write_fn: Callable[[Path, list[OrderItemRow]], None],
    read_fn: Callable[[Path], list[dict[str, T]]],
    parse_row_fn: Callable[[dict[str, T]], OrderItemRow],
) -> None:
    # Made once for a smaller batch for library loading so it doesn't count for measurements
    warmup_path = file_path.with_name("warmup-" + file_path.name)
    write_fn(warmup_path, rows[:100])
    read_fn(warmup_path)
    warmup_path.unlink()

    # Write read and parse performance test
    _, write_seconds = _avg_of(lambda: write_fn(file_path, rows))
    read_back_file, read_seconds = _avg_of(lambda: read_fn(file_path))
    parsed_results, parse_seconds = _avg_of(lambda: [parse_row_fn(item) for item in read_back_file])
    changed_columns = find_changed_columns_after_round_trip(rows, read_back_file)

    # File size in MiB conversion
    size_bytes = file_path.stat().st_size
    size_mb = size_bytes / 1_000_000

    # Output performance and file size
    print(f"PERFORMANCE MEASUREMENTS average of {TIMING_RUNS} runs for {file_path.suffix} files: ")
    print(f"Number of rows: {len(rows):_}")
    print(f"Write took {write_seconds:.2f} seconds")
    print(f"Read took {read_seconds:.2f} seconds")
    print(f"Parsing took {parse_seconds:.2f} seconds")
    print(f"Restored after parsing: {parsed_results == rows}")
    print(f"File size: {size_mb:.2f} MB")
    print(f"These columns suffered modifications: {changed_columns}")
    print("---------------------------------------------------------------------")


def find_changed_columns_after_round_trip(
    original: Sequence[OrderItemRow], read_back: Sequence[Mapping[str, object]]
) -> list[str]:
    """Return the columns whose type or value differs after the round-trip."""

    changed_columns: set[str] = set()
    for original_item, read_back_item in zip(original, read_back, strict=True):
        for column in ORDER_ITEM_COLUMNS:
            original_value = original_item[column]
            read_back_value = read_back_item[column]
            if (
                type(original_value) is not type(read_back_value)
                or original_value != read_back_value
            ):
                changed_columns.add(column)
    return sorted(changed_columns)


def _avg_of(operation: Callable[[], T]) -> tuple[T, float]:
    """Takes a method as lambda function, returns the result and avg time needed to complete it."""
    runs = [_timed(operation) for _ in range(TIMING_RUNS)]
    result = runs[-1][0]
    return result, mean(seconds for _, seconds in runs)


def _timed(operation: Callable[[], T]) -> tuple[T, float]:
    start = time.perf_counter()
    result = operation()
    return result, time.perf_counter() - start


if __name__ == "__main__":
    main()
