"""Unit tests for TelemetryEnrichmentService (extracted metric pipeline)."""

import unittest
from unittest import mock

from energy_system.application.enrichment import TelemetryEnrichmentService


class TestTelemetryEnrichment(unittest.TestCase):
    def setUp(self):
        self.svc = TelemetryEnrichmentService(
            battery_capacity_mah=10000.0,
            battery_initial_soc=80.0,
        )

    def test_enrich_returns_same_dict_and_sets_metrics(self):
        sample = {
            "temperature": 25.0,
            "humidity": 50.0,
            "pwr_mw": 1200,
            "solar_pwr_mw": 3000,
            "solar_bus_v": 12.0,
            "solar_current_ma": 250.0,
        }
        out = self.svc.enrich(sample)

        self.assertIs(out, sample)
        # comfort is a 0..1 score derived from temp/humidity
        self.assertIn("comfort_score", sample)
        self.assertGreaterEqual(sample["comfort_score"], 0.0)
        self.assertLessEqual(sample["comfort_score"], 1.0)
        # power from pwr_mw (mW -> W)
        self.assertAlmostEqual(sample["power_w"], 1.2)
        # solar power from pwr_mw key
        self.assertAlmostEqual(sample["solar_power_w"], 3.0)
        # energy/soc start at defaults on first sample (no prior timestamp)
        self.assertEqual(sample["energy_wh"], 0.0)
        self.assertEqual(sample["solar_energy_wh"], 0.0)
        self.assertAlmostEqual(sample["soc_percent"], 80.0)

    def test_comfort_defaults_when_fields_missing(self):
        sample = {}
        self.svc.enrich(sample)
        # pick() falls back to 25.0 / 50.0 → TCI 0.5, humidity 1.0 → 0.6*0.5+0.4 = 0.7
        self.assertAlmostEqual(sample["comfort_score"], 0.7)

    def test_soc_advanced_on_second_sample(self):
        clock = {"t": 1000.0}
        with mock.patch("time.time", side_effect=lambda: clock["t"]):
            self.svc.enrich({"solar_current_ma": 0.0})
            clock["t"] = 1000.0 + 3600.0  # 1 hour later
            # 1000 mA of charging current over 1h = 1000 mAh = 10% of 10000 mAh
            self.svc.enrich({"solar_current_ma": 1000.0})
        self.assertAlmostEqual(
            self.svc.battery_soc.snapshot().soc_percent, 90.0, places=6
        )


if __name__ == "__main__":
    unittest.main()
