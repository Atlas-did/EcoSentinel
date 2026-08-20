"""Unit tests for the API services layer (no HTTP involved)."""

import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from energy_system.api.services import ApiServices
from energy_system.config.runtime_config import AppConfig
from energy_system.persistence.jsonl_repository import JsonlTelemetryRepository


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestApiServices(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        cfg = AppConfig(run_label="saving")
        repo = JsonlTelemetryRepository(self.dir, run_label="saving")
        self.svc = ApiServices(repo, cfg)

    def tearDown(self):
        self._tmp.cleanup()

    def _hardware(self, lines):
        _write(self.dir / "hardware_saving.jsonl", lines)

    def test_snapshot_no_log(self):
        snap = self.svc.snapshot()
        self.assertEqual(snap.errors, ["no_log_file"])

    def test_snapshot_maps_fields(self):
        self._hardware([json.dumps({
            "timestamp": "2026-08-20T08:00:00",
            "temperature": 25.0,
            "humidity": 52.0,
            "relays": [1, 0],
            "errors": ["bus_warn"],
        })])
        snap = self.svc.snapshot()
        self.assertEqual(snap.temperature, 25.0)
        self.assertEqual(snap.humidity, 52.0)
        self.assertEqual(snap.relays, [1, 0])
        self.assertEqual(snap.errors, ["bus_warn"])

    def test_chart_scales_comfort_to_percent(self):
        recent = (datetime.now() - timedelta(minutes=1)).isoformat()
        self._hardware([json.dumps({
            "timestamp": recent,
            "temperature": 24.0,
            "comfort_score": 0.78,
        })])
        points = self.svc.chart(range_="1h")
        self.assertEqual(points[0].temp, 24.0)
        self.assertEqual(points[0].comfort_score, 78.0)

    def test_energy_summary_uses_daily_files(self):
        today = date.today().isoformat()
        _write(self.dir / f"daily_energy_baseline_{today}.json",
               [json.dumps({"load_energy_wh": 10000})])
        _write(self.dir / f"daily_energy_saving_{today}.json",
               [json.dumps({"load_energy_wh": 7000})])
        summary = self.svc.energy_summary()
        self.assertEqual(summary.baseline_kwh, 10.0)
        self.assertEqual(summary.saving_kwh, 7.0)
        self.assertEqual(summary.energy_saved_kwh, 3.0)
        self.assertAlmostEqual(summary.saving_rate, 30.0, places=1)

    def test_compute_sampling_rate(self):
        now = datetime(2026, 8, 20, 8, 0, 0)
        rows = [
            {"timestamp": (now + timedelta(seconds=i * 10)).isoformat()}
            for i in range(4)
        ]
        rate = ApiServices._compute_sampling_rate(rows)
        self.assertAlmostEqual(rate, 3 / 30.0, places=6)

    def test_compute_sampling_rate_insufficient(self):
        self.assertIsNone(ApiServices._compute_sampling_rate([]))
        self.assertIsNone(ApiServices._compute_sampling_rate([{"timestamp": "x"}]))

    def test_health_shape(self):
        self._hardware([json.dumps({
            "timestamp": "2026-08-20T08:00:00",
            "temperature": 25.0,
            "power_w": 10.0,
        })])
        health = self.svc.health()
        self.assertTrue(health.serial_connected)
        self.assertTrue(health.sensors_online.temperature)
        self.assertFalse(health.sensors_online.humidity)


if __name__ == "__main__":
    unittest.main()
