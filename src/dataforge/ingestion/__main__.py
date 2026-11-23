"""Command line: `python -m dataforge.ingestion`."""

from datetime import UTC, datetime

from dataforge.db import connect
from dataforge.ingestion.extract import extract_changes, extract_schema
from dataforge.ingestion.landing import write_landing_file
from dataforge.ingestion.watermark import read_watermark, save_watermark
from dataforge.paths import LANDING_DIR, WATERMARK_FILE


def main() -> None:
    with connect() as conn:
        table_name = "order_item"
        extracted_at = datetime.now(UTC)
        batch_id = extracted_at.strftime("%Y%m%dT%H%M%SZ")
        watermark = read_watermark(WATERMARK_FILE, table_name)
        rows = extract_changes(conn, table_name, watermark)
        if len(rows) != 0:
            schema = extract_schema(conn, table_name)
            write_landing_file(LANDING_DIR, table_name, batch_id, extracted_at, rows, schema)
            newest_row = max(row["updated_at"] for row in rows)
            last_updated = max(newest_row, watermark) if watermark is not None else newest_row
            save_watermark(WATERMARK_FILE, table_name, last_updated)


if __name__ == "__main__":
    main()
