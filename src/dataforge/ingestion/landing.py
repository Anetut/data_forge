"""Writes extracted rows to Parquet landing files."""

from pathlib import Path
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq


def write_landing_file(
    directory: Path,
    table_name: str,
    batch_id: str,
    rows: list[dict[str, object]],
    schema: pa.Schema,
) -> Path:

    file_path = directory / table_name / f"{batch_id}.parquet"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    processed_rows = [_to_parquet_row(row) for row in rows]
    table = pa.Table.from_pylist(processed_rows, schema=schema)
    pq.write_table(table, file_path)
    return file_path


def _to_parquet_row(row: dict[str, object]) -> dict[str, object]:
    return {key: str(value) if type(value) is UUID else value for key, value in row.items()}
