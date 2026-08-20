"""Unit tests for DashboardDataClient (unified, availability-aware reads)."""

import json
import tempfile
import unittest
from pathlib import Path

from dashboard.data_client import DashboardDataClient


class TestDashboardDataClient(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.client = DashboardDataClient(self.root, run_label="saving")

    def tearDown(self):
        self.tmp.cleanup()

    def _write_hardware(self, label, rows):
        p = self.root / "logs" / f"hardware_{label}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    def test_snapshot_ok_and_tracks_availability(self):
        self._write_hardware("saving", [
            {"timestamp": "2026-08-20T08:00:00", "temperature": 24.0, "energy_wh": 10.0},
            {"timestamp": "2026-08-20T08:05:00", "temperature": 25.0, "energy_wh": 12.0},
        ])
        res = self.client.snapshot()
        self.assertTrue(res.ok)
        self.assertEqual(res.data["energy_wh"], 12.0)
        self.assertTrue(self.client.available)
        self.assertIsNotNone(self.client.last_success_at)

    def test_snapshot_missing_returns_failure_state(self):
        res = self.client.snapshot()
        self.assertFalse(res.ok)
        self.assertEqual(res.reason, "no_log_data")
        self.assertFalse(self.client.available)
        self.assertEqual(self.client.last_error, "no_log_data")

    def test_baseline_vs_saving_requires_both(self):
        self._write_hardware("baseline", [{"energy_wh": 100.0}])
        res = self.client.baseline_vs_saving()
        self.assertFalse(res.ok)  # saving log missing
        self.assertEqual(res.reason, "missing_baseline_or_saving_log")

        self._write_hardware("saving", [{"energy_wh": 60.0}])
        res = self.client.baseline_vs_saving()
        self.assertTrue(res.ok)
        self.assertEqual(len(res.data["baseline"]), 1)
        self.assertEqual(len(res.data["saving"]), 1)

    def test_tail_empty_is_failure(self):
        res = self.client.tail()
        self.assertFalse(res.ok)
        self.assertIsNone(res.data)


if __name__ == "__main__":
    unittest.main()
