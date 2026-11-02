# Architecture (draft)

> Draft. It will be revised as the design is reviewed, with each change recorded as an [ADR](decisions/).

## Data flow

```mermaid
flowchart LR
    subgraph Sources
        GEN[Data generator<br/>CSV / JSON / Parquet]
        PG[(PostgreSQL<br/>operational DB)]
        API[REST APIs]
        EVT[Events<br/>Event Hubs]
    end

    ING[Ingestion<br/>Python + Pydantic validation]

    subgraph Lakehouse["Lakehouse (Delta Lake)"]
        B[(Bronze<br/>raw + lineage)]
        S[(Silver<br/>clean, deduped, validated)]
        G[(Gold<br/>business metrics)]
    end

    GEN --> ING
    PG --> ING
    API --> ING
    EVT -.streaming.-> B
    ING --> B
    B -->|PySpark| S
    S -->|PySpark| G
    G --> BI[Analytics / SQL]
    G --> SVC[FastAPI services]
    SVC --> PG
```

## Layers

| Layer | Purpose | Key problems it solves |
| --- | --- | --- |
| Bronze | Raw data as received, plus ingestion timestamp and source | Replayability, auditing, no data loss |
| Silver | Cleaned, deduplicated, validated, conformed | Data quality, updates, late-arriving data |
| Gold | Aggregated, business-ready tables | Fast, simple consumption |

## Components

To be filled in as each is built. Placeholder for each: responsibility, inputs/outputs, owner module, failure modes.

## Local vs. Azure

| Concern | Local | Azure |
| --- | --- | --- |
| Object storage | `data/` directory | ADLS Gen2 |
| Processing | local PySpark | Azure Databricks |
| Secrets | `.env` | Key Vault |
| Orchestration | scripts | Databricks Workflows / ADF |
| Events | local stand-in | Event Hubs |
