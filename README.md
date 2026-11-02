# DataForge

An end-to-end data processing platform for a simulated e-commerce business. It ingests messy data from several sources, cleans and models it with **PySpark + Delta Lake** in a **Bronze / Silver / Gold** (medallion) layout, and serves it to analytics and operational services. It starts fully local and moves to **Azure Databricks + ADLS Gen2** in later phases.

> Status: **Phase 0 – foundation.** Repo scaffold only; no pipeline code yet.

## Stack

| Concern | Technology |
| --- | --- |
| Language | Python 3.11+ |
| Operational DB | PostgreSQL 16 (Docker) |
| Processing | Apache Spark / PySpark |
| Lakehouse | Delta Lake, Azure Databricks, ADLS Gen2 |
| Services | FastAPI, Pydantic |
| Streaming (optional) | Spark Structured Streaming, Azure Event Hubs |
| Quality | Pytest, Ruff, GitHub Actions |

## Repository layout

```
src/dataforge/   Shared Python package (config, logging, ingestion, validation, ...)
services/        FastAPI microservices (Phase 7)
spark/           PySpark jobs: bronze / silver / gold (Phase 3+)
databricks/      Databricks notebooks, job definitions, bundle config (Phase 4+)
sql/             PostgreSQL schema, init scripts and analytical queries
infra/           Azure infrastructure definitions (Phase 6)
notebooks/       Local exploration notebooks
data/            Generated datasets (git-ignored)
tests/           Unit and integration tests
docs/            Architecture, conventions, roadmap, ADRs
```

## Getting started (Windows / PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

copy .env.example .env
docker compose up -d postgres

ruff check .
pytest
```

Later phases add extras: `pip install -e ".[dev,ingest]"`, `".[dev,spark]"`, `".[dev,services]"`.

### Prerequisites

- Python 3.11+ (3.12 matches current Databricks runtimes best)
- Docker Desktop
- Git
- **Java 17 or 21** from Phase 3 on (needed by Spark; newer JDKs may not be supported by the pinned PySpark version). If a newer JDK is first on your `PATH`, point Spark at 21 for the current shell:
  ```powershell
  $env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-21.0.13.9-hotspot"
  ```

## Documentation

- [Architecture](docs/architecture.md)
- [Code conventions](docs/conventions.md)
- [Roadmap](docs/roadmap.md)
- [Architecture decision records](docs/decisions/)
