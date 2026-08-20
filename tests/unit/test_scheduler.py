"""Unit tests for the injectable fixed-interval Scheduler."""

import unittest

from energy_system.application.scheduler import Scheduler


class TestScheduler(unittest.TestCase):
    def test_advances_tick_and_sleeps(self):
        clock = {"t": 1000.0}
        slept = []

        sched = Scheduler(
            monotonic=lambda: clock["t"],
            sleep=slept.append,
        )
        nxt = sched.wait_until_next_tick(1000.0, 5.0)
        self.assertEqual(nxt, 1005.0)
        self.assertEqual(slept, [5.0])

    def test_no_sleep_on_overrun(self):
        clock = {"t": 1020.0}
        slept = []

        sched = Scheduler(monotonic=lambda: clock["t"], sleep=slept.append)
        nxt = sched.wait_until_next_tick(1000.0, 5.0)
        self.assertEqual(nxt, 1005.0)
        self.assertEqual(slept, [])


if __name__ == "__main__":
    unittest.main()
