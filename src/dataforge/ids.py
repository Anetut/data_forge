"""ID helpers shared by the generator, ingestion and the Spark jobs."""

import random
import uuid
from datetime import datetime


def new_uuid7(rand_gen: random.Random, created_at: datetime) -> uuid.UUID:
    """UUIDv7: 48-bit Unix milliseconds followed by random bits, so IDs sort by creation time.

    Time and randomness are arguments, so generated data is reproducible.
    """
    if created_at.tzinfo is None:
        raise ValueError(f"naive datetime {created_at!r}: timestamps must carry a UTC offset")
    unix_ms = int(created_at.timestamp() * 1000)
    value = (unix_ms << 80) | rand_gen.getrandbits(80)
    value = (value & ~(0xF << 76)) | (0x7 << 76)  # version 7
    value = (value & ~(0x3 << 62)) | (0x2 << 62)  # RFC 9562 variant
    return uuid.UUID(int=value)


def uuid7_time_ms(value: uuid.UUID) -> int:
    """Unix milliseconds stored in the first 48 bits of a UUIDv7."""
    return value.int >> 80
