from pathlib import Path
from typing import Any

import pytest

from dataforge.file_formats import FORMATS, format_for
from dataforge.file_formats.csv_format import CsvFormat
from dataforge.file_formats.file_format import FileFormat
from dataforge.file_formats.jsonl_format import JsonlFormat
from dataforge.file_formats.parquet_format import ParquetFormat


def test_every_format_matches_the_protocol():
    # Checked by Pyright, not at runtime: a wrong method name or signature fails CI here.
    csv_format: FileFormat[str] = CsvFormat()
    jsonl_format: FileFormat[object] = JsonlFormat()
    parquet_format: FileFormat[Any] = ParquetFormat()
    assert [csv_format.suffix, jsonl_format.suffix, parquet_format.suffix] == list(FORMATS)


@pytest.mark.parametrize("fmt", FORMATS.values(), ids=FORMATS.keys())
def test_rows_survive_a_round_trip(fmt, items, tmp_path):
    file_path = tmp_path / f"items{fmt.suffix}"
    fmt.write(file_path, items)
    assert [fmt.parse_row(raw_row) for raw_row in fmt.read(file_path)] == items


@pytest.mark.parametrize("fmt", FORMATS.values(), ids=FORMATS.keys())
def test_empty_file_reads_back_as_no_rows(fmt, tmp_path):
    file_path = tmp_path / f"items{fmt.suffix}"
    fmt.write(file_path, [])
    assert fmt.read(file_path) == []


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [("items.csv", CsvFormat), ("items.jsonl", JsonlFormat), ("items.parquet", ParquetFormat)],
)
def test_format_is_chosen_by_suffix(file_name, expected):
    assert type(format_for(Path("data") / file_name)) is expected


def test_unknown_suffix_is_rejected():
    with pytest.raises(ValueError, match=r"No format for \.xml is implemented"):
        format_for(Path("items.xml"))
