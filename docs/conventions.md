# Code conventions

Rules we follow when writing code in DataForge. Each section links to the official documentation behind it. If you disagree with a rule, change it and record the reason in an [ADR](decisions/).

Rules marked **[tooling]** are enforced by Ruff/CI. Everything else is enforced in code review.

## 1. Python

Official references:
- [PEP 8 – Style Guide](https://peps.python.org/pep-0008/)
- [PEP 257 – Docstrings](https://peps.python.org/pep-0257/)
- [PEP 484 – Type hints](https://peps.python.org/pep-0484/) and the [typing docs](https://docs.python.org/3/library/typing.html)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) (a more opinionated complement to PEP 8)
- [Ruff rules](https://docs.astral.sh/ruff/rules/)

Rules:
- Formatting and import order come from Ruff, line length 100. Never format by hand. **[tooling]**
- Target Python 3.11+. Use modern syntax: `list[str]`, `X | None`, `match` only when it clarifies. **[tooling: `UP`]**
- Naming: `snake_case` for functions, variables and modules, `PascalCase` for classes, `UPPER_SNAKE` for constants. Names say *what*, not *how*: `load_orders`, not `process_data`. **[tooling: `N`]**
- Type-hint every public function signature (parameters and return). Hints inside function bodies only when inference is unclear.
- Use `pathlib.Path`, not string paths. Use f-strings.
- Docstrings on public modules, classes and functions: one-line summary, then details only if the behaviour is not obvious from the name and types. Comments explain *why*, never *what*.
- Prefer small pure functions (data in, data out) over classes. Introduce a class only when it holds state or models a concept.
- No mutable default arguments, no bare `except:`, no `print` outside CLI entry points. **[tooling: `B`]**
- No premature abstraction: duplicate once, abstract on the third occurrence.

## 2. Project structure and layering

- Shared code lives in `src/dataforge/`. Executable entry points (CLI, Spark job, service `main`) stay thin: parse arguments, load config, call library code.
- Separate **I/O** (reading/writing files, DB, APIs) from **logic** (validation, transformation). Logic must be testable without Postgres, Spark clusters or network.
- Dependencies point one way: entry points → pipeline logic → shared utilities. Services never import from Spark jobs and vice versa; they share only `dataforge` modules.
- One module, one responsibility. If you need "and" to describe a file, split it.

## 3. Configuration and secrets

Official references:
- [The Twelve-Factor App: Config](https://12factor.net/config)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

Rules:
- All configuration comes from environment variables, parsed into one typed settings object (pydantic-settings). No `os.environ` reads scattered through the code.
- No secrets, connection strings or keys in code, notebooks, tests, or Git history. Locally use `.env` (git-ignored); on Azure use Key Vault.
- Every new variable is added to `.env.example` with a safe placeholder.
- Paths, hostnames, table names and thresholds are configuration, not literals in business logic.

## 4. Logging and errors

Official references:
- [Python logging HOWTO](https://docs.python.org/3/howto/logging.html)
- [Logging cookbook](https://docs.python.org/3/howto/logging-cookbook.html)

Rules:
- `logger = logging.getLogger(__name__)` per module; configure handlers once, at the entry point.
- Log events with context (dataset, batch id, row counts, duration), not prose. Use lazy formatting: `logger.info("loaded %d rows from %s", n, path)`.
- Never log secrets or personal data (emails, addresses, card data).
- Levels: `DEBUG` detail for developers, `INFO` pipeline milestones, `WARNING` recoverable anomalies (e.g. rejected records), `ERROR` a unit of work failed.
- Catch only exceptions you can handle. Define a small set of domain exceptions (e.g. `ValidationError`, `IngestionError`); do not swallow errors to keep a pipeline green.
- Bad records are **quarantined with a reason**, not silently dropped, and never crash the whole batch.
- Retries only for transient failures (network, throttling), with exponential backoff and a limit. Retried operations must be idempotent.

## 5. Testing

Official references:
- [pytest documentation](https://docs.pytest.org/en/stable/)
- [Good integration practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)

Rules:
- Tests live in `tests/`, mirroring the `src/dataforge/` layout. Names: `test_<behaviour>` describing the expectation, e.g. `test_duplicate_orders_keep_latest_update`.
- Arrange / act / assert, one behaviour per test. Prefer parametrised tests over loops.
- Unit tests are fast, deterministic, and need no network, Docker or Spark. Anything needing Postgres or Spark is marked `@pytest.mark.integration`.
- Test data is built in the test (small, explicit, readable), not loaded from the generated `data/` folder.
- Every bug fix starts with a failing test. Data-quality rules each get tests for the valid case, the invalid case and the edge (null, empty, boundary).
- Never rely on wall-clock time, randomness or ordering without controlling them (inject the clock, seed the generator, sort before asserting).

## 6. Data conventions

Official references:
- [Databricks medallion architecture](https://learn.microsoft.com/azure/databricks/lakehouse/medallion)
- [Delta Lake documentation](https://docs.delta.io/latest/index.html)
- [Apache Parquet documentation](https://parquet.apache.org/docs/)

Rules:
- Always define schemas explicitly. No `inferSchema` / type guessing outside exploration notebooks: inference is slow, non-deterministic and hides bad data.
- Column names: `snake_case`, singular, no spaces or special characters. Keys are `<entity>_id` (`customer_id`). Booleans start with `is_`/`has_`. Timestamps end with `_at`, dates with `_date`.
- Timestamps are **UTC**, timezone-aware, ISO 8601. Money is stored as integer minor units or `DECIMAL`, never float, together with a currency code.
- Table names: `snake_case`, plural for entity tables (`orders`), layer-qualified in the lakehouse: `bronze.orders`, `silver.orders`, `gold.daily_revenue`.
- **Bronze**: raw payload unchanged, plus metadata columns `_ingested_at`, `_source`, `_batch_id`. Append-only. No cleaning.
- **Silver**: typed, deduplicated, validated, conformed. Rejected rows go to a quarantine table with a reason code.
- **Gold**: business-ready aggregates, named after the business concept, documented grain ("one row per day per product").
- Every pipeline step must be **idempotent**: re-running with the same input produces the same output, with no duplicates. Prefer overwrite-by-partition or `MERGE` on a business key over blind appends (outside Bronze).
- Processing is incremental by default; full reloads are an explicit, documented operation.
- Every dataset has a documented grain, primary key, and owner.

## 7. PySpark

Official references:
- [PySpark API reference](https://spark.apache.org/docs/latest/api/python/index.html)
- [Spark SQL, DataFrames and Datasets Guide](https://spark.apache.org/docs/latest/sql-programming-guide.html)
- [Spark performance tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)
- [Delta Lake with PySpark](https://docs.delta.io/latest/quick-start.html)

Rules:
- Use the DataFrame API with built-in functions (`pyspark.sql.functions as F`). Python UDFs are a last resort (they serialize every row between the JVM and Python); prefer built-ins, then pandas UDFs.
- Write transformations as pure functions `DataFrame -> DataFrame` so they can be unit-tested on tiny DataFrames and chained with `.transform()`.
- Build the `SparkSession` in one place only; pass DataFrames or the session as arguments rather than creating sessions inside functions.
- Select only needed columns early, filter early, and avoid `collect()`, `toPandas()` and `count()` on large data unless intentional.
- Think about shuffles before writing a join or aggregation: broadcast small tables, and know which transformations are wide. Do not tune (`repartition`, caching, config) without measuring in the Spark UI.
- Write the explicit-schema, partitioned output deliberately: partition only on low-cardinality columns that queries filter on (usually a date), and avoid tiny files.
- Never rely on implicit ordering of rows.

## 8. SQL (PostgreSQL and Spark SQL)

Official references:
- [PostgreSQL documentation](https://www.postgresql.org/docs/current/)
- [Spark SQL reference](https://spark.apache.org/docs/latest/sql-ref.html)
- [Databricks SQL language reference](https://learn.microsoft.com/azure/databricks/sql/language-manual/)

Rules:
- Keywords in `UPPERCASE`, identifiers in `snake_case`, one clause per line, one selected column per line in non-trivial queries.
- Explicit `JOIN ... ON`, never comma joins. Qualify columns with a table alias when more than one table is involved.
- Prefer CTEs over deeply nested subqueries; name each CTE after what it contains.
- No `SELECT *` in anything persistent (views, jobs, application code).
- Be explicit about `NULL` handling (`COALESCE`, `IS NULL`) and about the grain of every result.
- Schema changes are versioned SQL files in `sql/` (never manual changes to the database). Every foreign key and frequently filtered column is considered for an index, and checked with `EXPLAIN ANALYZE` before and after.

## 9. APIs and services (FastAPI)

Official references:
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [Pydantic documentation](https://docs.pydantic.dev/latest/)
- [HTTP semantics, RFC 9110](https://www.rfc-editor.org/rfc/rfc9110)

Rules:
- Validate all external input at the boundary with Pydantic models; internal code works with validated types.
- Separate request/response models from persistence models. Do not expose database rows directly.
- Use correct HTTP verbs and status codes; errors return a consistent JSON body.
- Mutating endpoints and event consumers are idempotent (idempotency key or natural key).
- Each service owns its data. No service reads another service's database; they communicate via API or events.
- Every service exposes a health endpoint and logs a correlation/request id.

## 10. Docker and infrastructure

Official references:
- [Dockerfile best practices](https://docs.docker.com/build/building/best-practices/)
- [Compose file reference](https://docs.docker.com/reference/compose-file/)
- [Azure resource naming (Cloud Adoption Framework)](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming)

Rules:
- Pin image versions (`postgres:16`, not `latest`). Run containers as non-root where possible.
- Containers are disposable: state lives in named volumes, config in environment variables.
- Azure resources follow one naming scheme `<type>-dataforge-<env>` (for example `st`/`kv`/`dbw` abbreviations from the CAF list), tagged with `project=dataforge` and `env=dev`. Anything that can cost money is listed and costed in the docs *before* it is created.

## 11. Git and collaboration

Official references:
- [Conventional Commits](https://www.conventionalcommits.org/)
- [GitHub flow](https://docs.github.com/get-started/using-github/github-flow)
- [Pro Git book](https://git-scm.com/book)
- [ADR resources](https://adr.github.io/)

Rules:
- Small, focused commits with Conventional Commit messages: `feat(ingestion): validate order payloads`, `fix(silver): keep latest update per order`, `docs:`, `test:`, `chore:`.
- Work on short-lived branches (`feat/...`, `fix/...`) and merge to `main` through a pull request, even when working alone; CI must pass.
- Never commit generated data, `.env`, credentials, notebooks with outputs containing data, or virtualenvs.
- Non-obvious design decisions get an ADR in `docs/decisions/`.

## 12. Versioning

Official references:
- [Semantic Versioning](https://semver.org/)
- [PEP 440 – Version identifiers](https://peps.python.org/pep-0440/)

Rules:
- The version lives in one place: `__version__` in `src/dataforge/__init__.py`. `pyproject.toml` reads it from there; never edit it anywhere else.
- Every pull request that changes behaviour, public interfaces, schemas or dependencies bumps the version. Docs-, test- and CI-only changes may leave it unchanged.
- Follow SemVer: `PATCH` for backwards-compatible fixes, `MINOR` for backwards-compatible features, `MAJOR` for breaking changes (table schemas, public function signatures, API contracts). While the version is `0.x`, breaking changes bump `MINOR`.
- Releases are tagged `vX.Y.Z` on `main`.