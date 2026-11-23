"""Remembers how far each table has been extracted (the watermark)."""

import json
import os
from datetime import datetime
from pathlib import Path


def read_watermark(file_path: Path, table_name: str) -> datetime | None:
    content = _load(file_path).get(table_name)
    return datetime.fromisoformat(content) if content is not None else None


def save_watermark(file_path: Path, table_name: str, value: datetime) -> None:
    if value.tzinfo is None:
        raise ValueError("Watermark is missing timezone info")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = _load(file_path)
    content[table_name] = value.isoformat()
    temp_path = file_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(content), encoding="utf-8")
    os.replace(temp_path, file_path)


def _load(file_path: Path) -> dict[str, str]:
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))
