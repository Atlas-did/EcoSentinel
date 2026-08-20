"""Unit tests for the unified MetricSnapshot and EnergyAccountingConfig."""

import unittest

from energy_system.domain.metrics import (
    EnergyAccountingConfig,
    MetricSnapshot,
    descriptive_stats,
)


class TestMetricSnapshot(unittest.TestCase):
    def test_from_sensor_maps_fields(self):
        snap = MetricSnapshot.from_sensor({
            "comfort_score": 0.7,
            "power_w": 1.2,
            "energy_wh": 3.0,
            "solar_energy_wh": 0.5,
            "soc_percent": 90.0,
        })
        self.assertEqual(snap.comfort_score, 0.7)
        self.assertEqual(snap.power_w, 1.2)
        self.assertEqual(snap.energy_wh, 3.0)
        self.assertEqual(snap.soc_percent, 90.0)

    def test_missing_fields_are_none_or_zero(self):
        snap = MetricSnapshot.from_sensor({})
        self.assertIsNone(snap.comfort_score)
        self.assertIsNone(snap.power_w)
        self.assertEqual(snap.energy_wh, 0.0)
        self.assertIsNone(snap.soc_percent)

    def test_to_dict_roundtrip(self):
        data = MetricSnapshot(comfort_score=0.8, energy_wh=2.0).to_dict()
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["comfort_score"], 0.8)


class TestEnergyAccountingConfig(unittest.TestCase):
    def test_from_settings(self):
        acct = EnergyAccountingConfig.from_settings()
        self.assertAlmostEqual(acct.carbon_factor, 0.5708)
        self.assertAlmostEqual(acct.electricity_price_cny_per_kwh, 0.80)

    def test_carbon_summary_provenance(self):
        s = EnergyAccountingConfig.from_settings().carbon_summary()
        for key in ("value", "unit", "factor_source", "factor_version", "calculation_window"):
            self.assertIn(key, s)
        self.assertEqual(s["unit"], "kgCO2/kWh")

    def test_price_summary_provenance(self):
        s = EnergyAccountingConfig.from_settings().price_summary()
        self.assertEqual(s["unit"], "CNY/kWh")
        self.assertIn("factor_source", s)


class TestDescriptiveStats(unittest.TestCase):
    def test_empty_is_descriptive_only(self):
        s = descriptive_stats([])
        self.assertEqual(s["count"], 0)
        self.assertIsNone(s["mean"])
        self.assertTrue(s["descriptive_only"])

    def test_small_sample_flagged(self):
        s = descriptive_stats([1.0, 3.0])
        self.assertEqual(s["count"], 2)
        self.assertAlmostEqual(s["mean"], 2.0)
        self.assertTrue(s["descriptive_only"])

    def test_std_and_ci(self):
        s = descriptive_stats([2.0, 4.0])
        # sample std of [2,4] = sqrt(((2-3)^2 + (4-3)^2)/(2-1)) = sqrt(2)
        self.assertAlmostEqual(s["std"], 1.41421356, places=6)
        self.assertGreater(s["ci95"], 0)
        self.assertEqual(s["count"], 2)

    def test_none_values_ignored(self):
        s = descriptive_stats([1.0, None, 3.0])
        self.assertEqual(s["count"], 2)
        self.assertAlmostEqual(s["mean"], 2.0)


if __name__ == "__main__":
    unittest.main()
