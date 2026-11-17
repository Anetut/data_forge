"""Shared protocol for file formats."""

from pathlib import Path
from typing import Protocol, TypeVar

from dataforge.domain.order_item_row import OrderItemRow

RawValue = TypeVar("RawValue")


class FileFormat(Protocol[RawValue]):
    suffix: str

    def write(self, file_path: Path, rows: list[OrderItemRow]) -> None:
        """Write a list of `OrderItemRow` objects to a particular file."""
        ...

    def read(self, file_path: Path) -> list[dict[str, RawValue]]:
        """Load the file into one raw dict per row, without converting types."""
        ...

    def parse_row(self, raw_row: dict[str, RawValue]) -> OrderItemRow:
        """Convert one raw row from `read` into an `OrderItemRow`.
        Raise `ValueError` on bad values."""
        ...
