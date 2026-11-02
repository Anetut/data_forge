# ADR-0001: Single monorepo with one shared Python package

- Status: accepted
- Date: 2026-11-03

## Context

DataForge has ingestion code, Spark jobs, Databricks notebooks and a few services. A small team (initially one developer) needs to run and change all of them together.

## Decision

One Git repository. Shared code lives in the installable `dataforge` package under `src/`. Services, Spark jobs and Databricks assets live in top-level directories and import from that package. Dependencies are split into optional extras per phase in `pyproject.toml`.

## Alternatives considered

- One repo per service: realistic for large organisations, but heavy overhead at this size and obscures data flow.
- No shared package (scripts only): faster at first, but code duplication and untestable logic appear by Phase 3.

## Consequences

Atomic changes across components and a single CI pipeline. Services share a release cadence; split them only if that becomes a real problem.
