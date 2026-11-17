import json
from datetime import UTC, datetime

import pytest

from dataforge.ingestion.watermark import read_watermark, save_watermark


def test_read_watermark_when_file_does_not_exist(tmp_watermark_path, table_name):
    assert read_watermark(tmp_watermark_path, table_name) is None


def test_read_watermark_when_exists(tmp_watermark_path, table_name, watermark_text, watermark_date):
    tmp_watermark_path.write_text(json.dumps({table_name: watermark_text}))
    assert read_watermark(tmp_watermark_path, table_name) == watermark_date


def test_write_watermark_raises_error_for_non_utc_date(tmp_watermark_path, table_name):
    date_without_utc = datetime.fromisoformat("2024-01-02T00:00")
    with pytest.raises(ValueError, match="Watermark is missing timezone info"):
        save_watermark(tmp_watermark_path, table_name, date_without_utc)


def test_write_watermark_does_not_corrupt_file_with_faulty_write(
    tmp_watermark_path, crash_on_write
):
    old = datetime(2026, 11, 1, tzinfo=UTC)
    save_watermark(tmp_watermark_path, "order_item", old)
    crash_on_write()
    with pytest.raises(OSError):
        save_watermark(tmp_watermark_path, "order_item", datetime(2026, 11, 14, tzinfo=UTC))
    assert read_watermark(tmp_watermark_path, "order_item") == old


def test_write_watermark_round_trip(tmp_watermark_path):
    order_wmk = datetime(2026, 11, 1, tzinfo=UTC)
    order_item_wmk = datetime(2026, 8, 1, tzinfo=UTC)
    save_watermark(tmp_watermark_path, "order_item", order_item_wmk)
    save_watermark(tmp_watermark_path, "order", order_wmk)
    assert read_watermark(tmp_watermark_path, "order_item") == order_item_wmk
    assert read_watermark(tmp_watermark_path, "order") == order_wmk
