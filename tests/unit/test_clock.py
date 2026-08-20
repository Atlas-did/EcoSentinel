"""Unit tests for the Clock abstraction."""

import unittest
from datetime import datetime

from energy_system.core.clock import FakeClock, SystemClock


class TestFakeClock(unittest.TestCase):
    def test_advances_both_clocks_together(self):
        clock = FakeClock(start=datetime(2026, 1, 1, 8, 0, 0))
        before = clock.monotonic()
        clock.advance(10.5)
        self.assertEqual(clock.monotonic(), before + 10.5)
        self.assertEqual(clock.now(), datetime(2026, 1, 1, 8, 0, 10, 500000))

    def test_set_independently(self):
        clock = FakeClock()
        clock.set(monotonic=100.0)
        self.assertEqual(clock.monotonic(), 100.0)
        clock.set(now=datetime(2026, 6, 1, 12, 0, 0))
        self.assertEqual(clock.now(), datetime(2026, 6, 1, 12, 0, 0))
        # monotonic unchanged by a wall-clock-only set
        self.assertEqual(clock.monotonic(), 100.0)


class TestSystemClock(unittest.TestCase):
    def test_monotonic_increases(self):
        clock = SystemClock()
        a = clock.monotonic()
        b = clock.monotonic()
        self.assertGreaterEqual(b, a)

    def test_now_returns_datetime(self):
        self.assertIsInstance(SystemClock().now(), datetime)


if __name__ == "__main__":
    unittest.main()
