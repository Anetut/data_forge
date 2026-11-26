# Decisions

1. **Prices as string** (`"100.15"`), never float. Floats can't store most decimals exactly.
2. **All timestamps should be UTC** - a timestamp without one is rejected. Assuming missing timezone means standard UTC, might provide faulty reports shifted by hours.
3. **Parquet schema <s>is written by hand</s>** Extracts take it from the source db table. The benchmark uses a fixed hand-written to match the Postgres table. No inference.
4. <s>**If CSV is used: an empty cell means null** - fine as long as there are no free-text columns.</s> outdated
5. **Won't use CSV** - Even if CSV is smaller than JSON Lines, ambiguity of null vs `""`, lack of types and too much parsing rules makes it harder to manage
6. **Landing data format follows the source** - Parquet for database extracts, JSON Lines for JSON feeds.
7. **Processed data as Parquet** - small file size, exact types, very fast to scan and aggregate
8. <s>**UUIDs are stored as 16-byte binary** (reversed, see 10). Spark and Delta have no UUID type, so binary IDs would need converting whenever they are read, filtered by hand, or joined with string IDs - the downside. The upside - faster read/write times from disk, smaller file size. The slower reading is pyarrow's conversion to Python objects; reading the file itself is faster </s>
9. **UUIDv7 whenever possible**. Faster indexing and processing. v7 IDs are time-ordered, so new rows go to the end of the index instead of random pages
10. **UUIDs as strings** - 8 reversed after finding out that Delta keeps no statistics on binary columns and liquid clustering can't use them, so file skipping wouldn't be possible with binary UUIDs
11. **Buffer time before watermark for extraction** - there can be late arriving transactions happening after changes were extracted but with an older timestamp. A couple of minutes (10) of buffer is a decent tradeoff for this
