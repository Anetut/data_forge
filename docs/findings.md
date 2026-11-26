# Findings

Measurements and things discovered while building the platform, with the setup to reproduce them.
Decisions based on them are in [decisions.md](decisions.md).

## 1. Parsing, reading and writing times

**Setup:** round-trip of 100 000 `order_item` rows (`dataforge.format_benchmark`, seed 31, mean of 3 runs after warm-up).

- AMD Ryzen 7, 32 GB RAM DDR4-3000, SSD PCIe 4
- Python 3.13, pyarrow 26, Windows 11

Data from `dataforge.generator`: UUIDv7 IDs, rows in time order, about 2.2 items per order, foreign keys drawn from realistic pools.

**Results:**

| | CSV | JSON Lines | Parquet | Parquet with uuids as binary (measured with 2c5a822 commit) |
| --- | --- | --- | --- | --- |
| Write | 1.78 s | 2.44 s | 1.04 s | 0.61 s (−41.3%) |
| Read to Python dicts | 0.56 s | 0.61 s | 2.06 s | 2.53 s (+22.8%) |
| Parse to typed rows | 1.50 s | 1.51 s | 1.27 s | 1.17 s (−7.9%) |
| File Size | 27.26 MB | 49.77 MB | 6.74 MB | 4.96 MB (−26.4%) |
| Columns changed on raw read | 12 of 12 | 10 of 12 | 5 of 12 | 5 of 12 |
|

Percentages: binary vs Parquet, minus = less.

Read split into reading the file and converting it to Python objects:

| | Parquet | Parquet with uuids as binary (measured with 2c5a822 commit) |
| --- | --- | --- |
| File -> Arrow table | 0.011 s | 0.009 s |
| Arrow table -> Python dicts | 2.06 s | 2.42 s |
|

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
|

**Conclusion:** Parquet for database extracts and processed data, no CSV (decisions 5, 6, 7). Binary UUIDs were smaller and faster to write, but were reversed for Delta reasons (decisions 8, 10).

## 2. Extraction test: what an `updated_at` watermark misses (2026-11-24)

**Setup:** version 0.7.0 (commit 5003e79), extraction with a 10-minute lookback (decision 11). Times below are UTC+2; the watermark file stores them in UTC.

**What happened:**

- The DB was filled with data (fill-db --scale 3 created 200_773 rows in order_item).
- The first extract loaded everything into the parquet file, saving the watermark as the latest updated_at found (22:30:36, stored as 20:30:36 UTC).
- An activity was simulated, which introduced these changes into order_items:

  | Action | Row count |
  | --- | --- |
  | Pending → Shipped | 110 |
  | Shipped → Delivered | 345 |
  | Pending → Cancelled | 5 |
  | Delivered → Returned | 371 |
  | **Status updates in total** => 831 existing ids got updated | **831** |
  | New orders, which generated 695 order_items | 300 |
  | Late orders, which generated 51 order_items | 20 |
  | **=> new ids** | **746** |
  | Hard deletes on order_item, gone without a trace | 5 |

  Postgres after activity: 200_773 + 746 − 5 = 201_514 rows.

- Another extract took place after activity, which counted 1_591 rows, from which:
  - 746 new ids (ids that exist in the second file and not in initial)
  - 831 ids that exist in both files, but have a different updated_at timestamp
  - 14 ids as a consequence of 10 minutes lookback (extraction started from watermark - 10 mins) = ids that are exactly the same in both files

- Querying the ids from initial file which do not exist into the table returned 5 rows (the ones who got deleted without a trace), so the files do not show any logs about it

- 181 of the 746 new rows had an updated_at older than the first watermark (22:23:10 to 22:30:06). They were inserted after the first extract, but the generator wrote their simulated business time into updated_at, and the trigger only set it on UPDATE. Only the lookback caught them (oldest one about 2.5 minutes inside the window); `updated_at > watermark` alone would have skipped them silently.

**Conclusion:**

- Hard deletes are invisible to an `updated_at` watermark: downstream the 5 rows stay as if they still existed.
- The lookback costs a few duplicates (14) and saved 181 rows here.
- `updated_at` is only reliable if the database sets it on insert as well as on update.
