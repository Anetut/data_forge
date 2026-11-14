# Decisions

1. **Prices as string** (`"100.15"`), never float. Floats can't store most decimals exactly.
2. **All timestamps should be UTC** - a timestamp without one is rejected. Assuming missing timezone means standard UTC, might provide faulty reports shifted by hours.
3. **Parquet schema is written by hand** to match the Postgres table. No inference.
4. **If CSV is used: an empty cell means null** - fine as long as there are no free-text columns.
5. **Won't use CSV** - Even if CSV is smaller, ambiguity of null vs `""`, lack of types and too much parsing rules makes it harder to manage
6. **Landing data as JSON Lines** - easy to append, easy to change when schema changes, readable, easy to work with.
7. **Processed data as Parquet** - small file size, exact types, very fast to scan and aggregate
8. **UUIDs are stored as 16-byte binary**. Spark and Delta have no UUID type, so binary IDs would need converting whenever they are read, filtered by hand, or joined with string IDs - the downside. The upside - faster read/write times from disk, smaller file size. The slower reading is pyarrow's conversion to Python objects; reading the file itself is faster
9. **UUIDv7 whenever possible**. Faster indexing and processing



# Experiment


Round-trip of 100 000 `order_item` rows (`dataforge.compare_formats_module`, seed 31, mean of 3 runs after warm-up):

AMD Ryzen 7, 32 GB RAM DDR4-3000, SSD PCIe 4
Python 3.13, pyarrow 26, Windows 11

Data from `dataforge.generator`: UUIDv7 IDs, rows in time order, about 2.2 items per order, foreign keys drawn from realistic pools.

| | CSV | JSON Lines | Parquet | Parquet with uuids as binary |
| --- | --- | --- | --- | --- |
| Write | 1.78 s | 2.44 s | 1.04 s | 0.61 s (−41.3%) |
| Read to Python dicts | 0.56 s | 0.61 s | 2.06 s | 2.53 s (+22.8%) |
| Parse to typed rows | 1.50 s | 1.51 s | 1.27 s | 1.17 s (−7.9%) |
| File Size | 27.26 MB | 49.77 MB | 6.74 MB | 4.96 MB (−26.4%) |
| Columns changed on raw read | 12 of 12 | 10 of 12 | 5 of 12 | 5 of 12 |


Percentages: binary vs Parquet, minus = less.

Read split into reading the file and converting it to Python objects:

| | Parquet | Parquet with uuids as binary |
| --- | --- | --- |
| File -> Arrow table | 0.011 s | 0.009 s |
| Arrow table -> Python dicts | 2.06 s | 2.42 s |

Slower read times is due to python processing, so it isn't a reliable indicator for binary vs string uuid.

Earlier run with the first generator (four random v4 IDs per row, nothing repeating): Parquet 18.36 MB, binary 10.80 MB. With realistic data the foreign keys repeat and dictionary-encode whatever their type, so only `id` stays expensive.

Same test environment, 1 000 000 rows (first generator, random v4 IDs, not re-run):
| | CSV | JSON Lines | Parquet |
| --- | --- | --- | --- |
| Write | 14.90 s | 20.51 s | 9.60 s |
| Read to Python dicts | 5.74 s | 0.58 s | 15.89 s |
| Parse to typed rows | 13.36 s | 14.05 s | 10.92 s |
| File Size | 252.28 MB | 479.27 MB | 175.35 MB |
| Columns changed on raw read | 12 of 12 | 10 of 12 | 5 of 12 |
| Read 2 of 12 columns | n/a | n/a | 0.39 s vs 16.18 s (41.6×) |
