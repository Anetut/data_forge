"""Reads changed rows and the column schema of a table from Postgres."""

from datetime import datetime, timedelta
from typing import Any, TypedDict, cast

import psycopg
import pyarrow as pa
from psycopg import sql
from psycopg.rows import dict_row

# buffer with a few minutes to avoid missing rows that were updated later due to slow transactions
BUFFER_TIME = timedelta(minutes=10)


class ColumnInfo(TypedDict):
    """One row of information_schema.columns, as selected by `extract_schema`."""

    column_name: str
    udt_name: str
    numeric_precision: int | None
    numeric_scale: int | None


def extract_changes(
    conn: psycopg.Connection,
    table_name: str,
    watermark: datetime | None,
) -> list[dict[str, Any]]:
    """All rows when watermark is None, otherwise rows updated after `watermark - buffer`."""
    if watermark is None:
        where, params = sql.SQL(""), ()
    else:
        where, params = sql.SQL("WHERE updated_at > %s"), (watermark - BUFFER_TIME,)
    query = sql.SQL("SELECT * FROM {table} {where} ORDER BY updated_at, id").format(
        table=sql.Identifier(table_name), where=where
    )
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def extract_schema(conn: psycopg.Connection, table_name: str) -> pa.Schema:
    query = sql.SQL(
        "SELECT column_name, udt_name, numeric_precision, numeric_scale "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position"
    )
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, (table_name,))
        # The SELECT above returns exactly the ColumnInfo keys; psycopg itself can't know that.
        columns = cast(list[ColumnInfo], cursor.fetchall())
    return _build_schema_from_column_types(columns)


def _build_schema_from_column_types(columns: list[ColumnInfo]) -> pa.Schema:
    fields = []
    for column in columns:
        arrow_type = _match_sql_data_type_to_arrow_type(
            column["udt_name"],
            column["numeric_precision"],
            column["numeric_scale"],
        )
        fields.append(pa.field(column["column_name"], arrow_type))
    return pa.schema(fields)


def _match_sql_data_type_to_arrow_type(
    data_type: str, precision: int | None, scale: int | None
) -> pa.DataType:
    match data_type:
        case (
            "uuid" | "varchar" | "order_status_enum" | "payment_method_enum" | "payment_status_enum"
        ):
            return pa.string()
        case "numeric":
            if precision is None or scale is None:
                raise ValueError("Numeric type without precision or scale")
            return pa.decimal128(precision, scale)
        case "int4":
            return pa.int32()
        case "int2":
            return pa.int16()
        case "bool":
            return pa.bool_()
        case "timestamptz":
            return pa.timestamp("us", tz="UTC")
        case "date":
            return pa.date32()
        case _:
            raise ValueError(f"Unsupported Postgres type: {data_type}")
