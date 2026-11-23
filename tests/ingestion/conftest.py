from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture
def tmp_watermark_path(tmp_path) -> Path:
    return tmp_path / "watermark.json"


@pytest.fixture
def table_name() -> str:
    return "test_table"


@pytest.fixture
def watermark_text() -> str:
    return "2024-01-02T00:00:00Z"


@pytest.fixture
def watermark_date(watermark_text) -> datetime:
    return datetime.fromisoformat(watermark_text)


@pytest.fixture
def crash_on_write(monkeypatch):
    """Call it to make every Path.write_text write half its data, then raise OSError."""
    real_write_text = Path.write_text

    def crash_halfway(self, data, *args, **kwargs):
        real_write_text(self, data[: len(data) // 2], *args, **kwargs)
        raise OSError("disk full")

    def switch_on() -> None:
        monkeypatch.setattr(Path, "write_text", crash_halfway)

    return switch_on
