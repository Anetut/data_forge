"""The feed's shared types: a raw JSON row, the kinds of issue, and a labelled feed line."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from dataforge.domain.order_item_row import OrderItemRow

RawRow = dict[str, object]


class Issue(StrEnum):
    # These rows break a rule, so validation must reject them.
    MISSING_VALUE = "missing_value"
    INVALID_VALUE = "invalid_value"
    BAD_FORMAT = "bad_format"
    ORPHAN_REFERENCE = "orphan_reference"
    # These rows are valid, and the later layers have to deal with them.
    DUPLICATE = "duplicate"
    LATE_ARRIVAL = "late_arrival"
    UPDATE = "update"


@dataclass(frozen=True)
class FeedLine:
    row: RawRow
    issue: Issue | None
    detail: str | None

    @classmethod
    def from_item(
        cls, item: OrderItemRow, issue: Issue | None = None, detail: str | None = None
    ) -> "FeedLine":
        """A feed line for an order item, in the JSON shape the partner sends."""
        return cls(FeedLine._to_raw(item), issue, detail)

    @staticmethod
    def _to_raw(item: OrderItemRow) -> RawRow:
        """The JSON shape the partner sends: strings for IDs, decimals and timestamps."""
        return {key: FeedLine._raw_value(value) for key, value in item.items()}

    @staticmethod
    def _raw_value(value: object) -> object:
        if isinstance(value, StrEnum):
            return value.value
        if isinstance(value, (UUID, Decimal)):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return value
