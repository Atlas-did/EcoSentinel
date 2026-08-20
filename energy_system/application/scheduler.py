"""Injectible fixed-interval loop cadence.

Extracted from ``EnergySystemApp._sleep_until`` so tests can drive the loop with
a fake clock and no real sleep.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

logger = logging.getLogger("Scheduler")


class Scheduler:
    def __init__(
        self,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._monotonic = monotonic
        self._sleep = sleep

    def wait_until_next_tick(self, next_tick: float, interval: float) -> float:
        """Sleep to maintain a fixed-interval loop cadence; returns the next tick."""
        next_tick += interval
        sleep_t = next_tick - self._monotonic()
        if sleep_t > 0:
            self._sleep(sleep_t)
        else:
            logger.warning(f"Loop overrun by {-sleep_t:.1f}s")
        return next_tick
