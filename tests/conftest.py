"""Fixtures shared by every test folder. Folder-specific ones live in each folder's conftest.py."""

import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest

from dataforge.db import connect

# Tests never touch the main database. Created by sql/init/02-create-test-database.sh.
TEST_DATABASE = os.environ.get("POSTGRES_TEST_DB", "dataforge_test")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Every test that uses the database (through `conn`) is an integration test."""
    for item in items:
        if "conn" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def now() -> datetime:
    """One fixed 'now' for the whole test run."""
    return datetime.now(UTC).replace(microsecond=0)


@pytest.fixture
def project_root(pytestconfig) -> Path:
    return pytestconfig.rootpath


@pytest.fixture
def conn():
    """Connection to the test database. Everything a test does is rolled back."""
    try:
        connection = connect(dbname=TEST_DATABASE)
    except psycopg.OperationalError as error:
        # Locally a missing Postgres is fine. In CI it must fail, or tests would pass by skipping.
        if os.environ.get("CI"):
            raise
        # The reason shows in the summary (-ra), so a missing test database doesn't go unnoticed.
        pytest.skip(f"Test database not reachable: {error}")
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()
