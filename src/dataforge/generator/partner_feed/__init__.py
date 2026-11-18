"""Partner feed: order-item rows in JSON Lines, with data quality issues injected on purpose."""

from dataforge.generator.partner_feed.builder import build_feed, write_feed
from dataforge.generator.partner_feed.lines import Issue

__all__ = ["Issue", "build_feed", "write_feed"]
