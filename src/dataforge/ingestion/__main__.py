"""Command line: `python -m dataforge.ingestion`."""

from dataforge.db import connect
from dataforge.ingestion.extract import extract_changes, extract_schema
from dataforge.ingestion.landing import write_landing_file
from dataforge.paths import LANDING_DIR


def main() -> None:
    with connect() as conn:
        table_name = "order_item"
        rows = extract_changes(conn, table_name, None)
        schema = extract_schema(conn, table_name)
        write_landing_file(LANDING_DIR, table_name, "", rows, schema)


if __name__ == "__main__":
    main()
