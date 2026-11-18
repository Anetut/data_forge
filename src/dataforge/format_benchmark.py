"""Compare CSV, JSON Lines and Parquet using generated order items."""

import random
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import TypeVar

from dataforge.domain.order_item_row import ORDER_ITEM_COLUMNS, OrderItemRow
from dataforge.file_formats import FORMATS
from dataforge.file_formats.file_format import FileFormat, RawValue
from dataforge.generator.orders import build_orders
from dataforge.generator.reference import Volumes, build_reference

SEED = 31
ROW_COUNT = 100_000
TIMING_RUNS = 3
# Assumes the src layout and an editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_OUTPUT_DIR = PROJECT_ROOT / "data"
T = TypeVar("T")


@dataclass(frozen=True)
class BenchmarkResult:
    suffix: str
    row_count: int
    write_seconds: float
    read_seconds: float
    parse_seconds: float
    size_bytes: int
    restored: bool
    changed_columns: tuple[str, ...]


def main() -> None:
    print("Creating mock data...")
    random_generator = random.Random(SEED)
    date_start = datetime(2020, 1, 1, tzinfo=UTC)
    date_end = datetime(2026, 1, 1, tzinfo=UTC)
    reference = build_reference(random_generator, Volumes(), before=date_start)
    # About 2.2 items per order; cut to exactly ROW_COUNT so results stay comparable.
    _, items = build_orders(random_generator, reference.sources, ROW_COUNT, date_start, date_end)
    rows = items[:ROW_COUNT]

    for fmt in FORMATS.values():
        result = benchmark(fmt, DATA_OUTPUT_DIR / f"order_items{fmt.suffix}", rows)
        print_result(result)


def benchmark(
    fmt: FileFormat[RawValue], file_path: Path, rows: list[OrderItemRow]
) -> BenchmarkResult:
    """Write, read and parse `rows` with `fmt`; return the measurements without printing."""
    # Made once for a smaller batch for library loading so it doesn't count for measurements
    warmup_path = file_path.with_name("warmup-" + file_path.name)
    fmt.write(warmup_path, rows[:100])
    fmt.read(warmup_path)
    warmup_path.unlink()

    _, write_seconds = _avg_of(lambda: fmt.write(file_path, rows))
    read_back_file, read_seconds = _avg_of(lambda: fmt.read(file_path))
    parsed_results, parse_seconds = _avg_of(
        lambda: [fmt.parse_row(item) for item in read_back_file]
    )
    changed_columns = find_changed_columns_after_round_trip(rows, read_back_file)

    return BenchmarkResult(
        suffix=fmt.suffix,
        row_count=len(rows),
        write_seconds=write_seconds,
        read_seconds=read_seconds,
        parse_seconds=parse_seconds,
        size_bytes=file_path.stat().st_size,
        restored=parsed_results == rows,
        changed_columns=tuple(changed_columns),
    )


def print_result(result: BenchmarkResult) -> None:
    print(f"PERFORMANCE MEASUREMENTS average of {TIMING_RUNS} runs for {result.suffix} files: ")
    print(f"Number of rows: {result.row_count:_}")
    print(f"Write took {result.write_seconds:.2f} seconds")
    print(f"Read took {result.read_seconds:.2f} seconds")
    print(f"Parsing took {result.parse_seconds:.2f} seconds")
    print(f"Restored after parsing: {result.restored}")
    print(f"File size: {result.size_bytes / 1_000_000:.2f} MB")
    print(f"These columns suffered modifications: {list(result.changed_columns)}")
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
