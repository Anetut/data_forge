# Roadmap

Each phase ends with working, tested software. Order may change; record why in an ADR.

Priority: **core** (required for the platform to work end to end), **supporting** (improves it), **optional** (can be deferred).

| Phase | Focus | Priority | Status |
| --- | --- | --- | --- |
| 0 | Repo foundation, tooling, CI | core | in progress |
| 1 | Operational database (PostgreSQL), schema design, file formats (CSV/JSON/Parquet) | core | todo |
| 2 | Synthetic data generator and ingestion with validation | core | todo |
| 3 | Batch processing with PySpark | core | todo |
| 4 | Databricks and Delta Lake: medallion layers, incremental loads, MERGE | core | todo |
| 5 | End-to-end pipelines: idempotency, retries, orchestration | core | todo |
| 6 | Azure: ADLS Gen2, Key Vault, monitoring | core | todo |
| 7 | FastAPI services and business events | supporting | todo |
| 8 | Streaming: Event Hubs, Structured Streaming | optional | todo |
| 9 | Production readiness: tests, data quality, CI/CD, docs | core | todo |

## Dependencies

```
0 → 1 → 2 → 3 → 4 → 5 → 6 → 9
              └──────→ 7 → 8 → 9
```

## Definition of done per phase

- Code runs from a clean checkout following the README
- Tests pass in CI
- Docs updated (architecture, ADRs for non-obvious decisions)
