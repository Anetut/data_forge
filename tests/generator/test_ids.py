import random
from datetime import UTC, datetime, timedelta

import pytest

from dataforge.ids import new_uuid7, uuid7_time_ms

AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_uuid7_has_version_7_and_rfc_variant():
    value = new_uuid7(random.Random(1), AT)
    assert value.version == 7
    assert value.variant == "specified in RFC 4122"


def test_uuid7_stores_the_creation_time():
    assert uuid7_time_ms(new_uuid7(random.Random(1), AT)) == int(AT.timestamp() * 1000)


def test_uuid7_sorts_by_creation_time_across_milliseconds():
    rand_gen = random.Random(1)
    times = [AT + timedelta(milliseconds=ms) for ms in range(50)]
    ids = [new_uuid7(rand_gen, at) for at in times]
    assert ids == sorted(ids)


def test_uuid7_is_reproducible_with_the_same_seed():
    assert new_uuid7(random.Random(7), AT) == new_uuid7(random.Random(7), AT)


def test_uuid7_rejects_naive_datetime():
    with pytest.raises(ValueError, match="naive"):
        new_uuid7(random.Random(1), datetime(2026, 1, 1))
