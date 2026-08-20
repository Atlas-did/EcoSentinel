"""Time abstraction: wall-clock (event time) vs. monotonic (elapsed time).

The two notions serve different purposes and must not be mixed:

- ``now()``       — wall-clock time, used for display and cross-record alignment.
- ``monotonic()`` — elapsed-seconds clock, used for timeouts, cooldowns and rate
                    limiting (immune to NTP/wall-clock jumps).

Production code should depend on the :class:`Clock` protocol and receive a clock
instance, so tests can advance time deterministically with :class:`FakeClock`.
"""

from __future__ import annotations

import time as _time
from datetime import datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...


class SystemClock:
    """Default clock backed by the real system clock."""

    def now(self) -> datetime:
        return datetime.now()

    def monotonic(self) -> float:
        return _time.monotonic()


class FakeClock:
    """Deterministic clock for tests and dry-runs.

    Both the wall-clock and monotonic clocks are advanced together by ``advance``.
    """

    def __init__(self, start: datetime | None = None, monotonic_start: float = 0.0):
        self._now = start or datetime(2026, 1, 1, 8, 0, 0)
        self._mono = float(monotonic_start)

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    def advance(self, seconds: float) -> None:
        """Advance both clocks by ``seconds`` (may be fractional)."""
        s = float(seconds)
        self._mono += s
        self._now += timedelta(seconds=s)

    def set(self, now: datetime | None = None, monotonic: float | None = None) -> None:
        """Set either clock independently."""
        if now is not None:
            self._now = now
        if monotonic is not None:
            self._mono = float(monotonic)
