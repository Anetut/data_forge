from datetime import UTC, datetime, timedelta

import pytest

from dataforge.generator.data.reference import Volumes


@pytest.fixture
def reference_time() -> datetime:
    """A fixed 'now' for generated data, so lifecycle assertions don't depend on the clock."""
    return datetime(2026, 6, 1, tzinfo=UTC)


@pytest.fixture
def history_start(reference_time) -> datetime:
    return reference_time - timedelta(days=365)


@pytest.fixture
def small_volumes() -> Volumes:
    return Volumes(customers=50, sellers=5, products=40, categories=5, offers=60)
