"""Fixtures shared by every test folder. Folder-specific ones live in each folder's conftest.py."""

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import psycopg
import pytest

from dataforge.db import connect

# Tests never touch the main database. Created by sql/init/01-create-test-database.sh,
# rebuilt from the migrations at the start of every test run (`test_database`).
TEST_DATABASE = os.environ.get("POSTGRES_TEST_DB", "dataforge_test")


def _skip_locally_fail_in_ci(reason: str) -> NoReturn:
    # Locally a missing Postgres is fine. In CI it must fail, or tests would pass by skipping.
    if os.environ.get("CI"):
        pytest.fail(reason)
    # The reason shows in the summary (-ra), so a missing test database doesn't go unnoticed.
    pytest.skip(reason)


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


@pytest.fixture(scope="session")
def test_database(pytestconfig) -> None:
    """Drop the test database's schema and apply every migration, once per test run.
    Nobody has to remember to migrate it, and leftovers from earlier runs are gone."""
    try:
        docker = subprocess.run(["docker", "info"], capture_output=True)
    except FileNotFoundError:
        _skip_locally_fail_in_ci("Docker is not installed: test database not rebuilt")
    if docker.returncode != 0:
        _skip_locally_fail_in_ci("Docker is not running: test database not rebuilt")
    result = subprocess.run(
        ["docker", "compose", "run", "--rm", "migrate-test"],
        cwd=pytestconfig.rootpath,
        capture_output=True,
        text=True,
    )
    # Docker runs, so a failure here is a broken migration: never skip it, even locally.
    if result.returncode != 0:
        pytest.fail(f"Test database rebuild failed:\n{result.stdout}{result.stderr}")


@pytest.fixture
def conn(test_database):
    """Connection to the test database. Everything a test does is rolled back."""
    try:
        connection = connect(dbname=TEST_DATABASE)
    except psycopg.OperationalError as error:
        _skip_locally_fail_in_ci(f"Test database not reachable: {error}")
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()
