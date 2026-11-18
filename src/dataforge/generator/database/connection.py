"""Connection to the local Postgres, with the same settings docker-compose uses."""

import os
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def connect() -> psycopg.Connection:
    """Connect with the settings docker-compose uses: environment, then `.env`, then defaults."""
    settings = _read_env_file(PROJECT_ROOT / ".env") | os.environ

    def setting(name: str, default: str) -> str:
        return settings.get(name, default)

    return psycopg.connect(
        host=setting("POSTGRES_HOST", "localhost"),
        port=int(setting("POSTGRES_PORT", "5432")),
        user=setting("POSTGRES_USER", "dataforge"),
        password=setting("POSTGRES_PASSWORD", "dataforge_local_only"),
        dbname=setting("POSTGRES_DB", "dataforge"),
        # Fail fast when Postgres isn't running instead of retrying for minutes.
        connect_timeout=5,
    )


def _read_env_file(path: Path) -> dict[str, str]:
    """Read KEY=value lines and skip comments and blank lines. That's enough for our .env."""
    if not path.exists():
        return {}
    pairs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and not key.strip().startswith("#"):
            pairs[key.strip()] = value.strip()
    return pairs
