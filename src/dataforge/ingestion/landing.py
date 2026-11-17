"""Writes extracted rows to Parquet landing files."""

import os
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq


def write_landing_file(
    directory: Path,
    table_name: str,
    batch_id: str,
    extracted_at: datetime,
    rows: list[dict[str, object]],
    schema: pa.Schema,
) -> Path:
    # TODO: add implementation for multiple batches
    file_path = directory / table_name / f"{batch_id}.parquet"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    processed_rows = [_to_parquet_row(row) for row in rows]
    table = pa.Table.from_pylist(processed_rows, schema=schema)
    table = _append_metadata(table, batch_id, extracted_at, f"postgres.{table_name}")
    tmp_path = file_path.with_suffix(".tmp")
    pq.write_table(table, tmp_path)
    os.replace(tmp_path, file_path)
    return file_path


def _append_metadata(
    table: pa.Table, batch_id: str, extracted_at: datetime, source: str
) -> pa.Table:
    rows = table.num_rows
    table = table.append_column(
        pa.field("_batch_id", pa.string()), pa.array([batch_id] * rows, pa.string())
    )
    table = table.append_column(
        pa.field("_extracted_at", pa.timestamp("us", tz="UTC")),
        pa.array([extracted_at] * rows, pa.timestamp("us", tz="UTC")),
    )
    table = table.append_column(
        pa.field("_source", pa.string()), pa.array([source] * rows, pa.string())
    )
    return table


def _to_parquet_row(row: dict[str, object]) -> dict[str, object]:
    return {key: str(value) if type(value) is UUID else value for key, value in row.items()}
