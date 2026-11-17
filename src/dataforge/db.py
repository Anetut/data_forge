"""Postgres connection with the same settings docker-compose uses."""

import os
from pathlib import Path

import psycopg

from dataforge.paths import PROJECT_ROOT


def connect(dbname: str | None = None) -> psycopg.Connection:
    """Connect with the settings docker-compose uses: environment, then `.env`, then defaults.

    `dbname` overrides POSTGRES_DB, e.g. for the tests' own database.
    """
    settings = _read_env_file(PROJECT_ROOT / ".env") | os.environ

    def setting(name: str, default: str) -> str:
        return settings.get(name, default)

    return psycopg.connect(
        host=setting("POSTGRES_HOST", "localhost"),
        port=int(setting("POSTGRES_PORT", "5432")),
        user=setting("POSTGRES_USER", "dataforge"),
        password=setting("POSTGRES_PASSWORD", "dataforge_local_only"),
        dbname=dbname or setting("POSTGRES_DB", "dataforge"),
        # Fail fast when Postgres isn't running instead of retrying for minutes.
        connect_timeout=5,
    )


def _read_env_file(path: Path) -> dict[str, str]:
    """KEY=value lines; comments and blank lines skipped. Enough for this project's .env."""
    if not path.exists():
        return {}
    pairs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and not key.strip().startswith("#"):
            pairs[key.strip()] = value.strip()
    return pairs
