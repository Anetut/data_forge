"""File formats for `OrderItemRow` data, chosen by file suffix.

Each format reads, writes and parses one file type. Callers use `FORMATS` or `format_for`
and depend only on the `FileFormat` protocol, never on a concrete class.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from dataforge.file_formats.csv_format import CsvFormat
from dataforge.file_formats.file_format import FileFormat
from dataforge.file_formats.jsonl_format import JsonlFormat
from dataforge.file_formats.parquet_format import ParquetFormat

FORMATS: Final[Mapping[str, FileFormat[Any]]] = {
    fmt.suffix: fmt for fmt in (CsvFormat(), JsonlFormat(), ParquetFormat())
}


def format_for(file_path: Path) -> FileFormat[Any]:
    """The format for a file, chosen by its suffix."""
    suffix = file_path.suffix
    if suffix not in FORMATS:
        raise ValueError(f"No format for {suffix} is implemented.")
    return FORMATS[suffix]
