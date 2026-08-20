"""Unit tests for energy accounting: hand-checked integration and timestamp safety."""

import unittest

from energy_system.power.energy_accounting import EnergyAccumulator


class TestEnergyAccumulator(unittest.TestCase):
    def test_hand_checked_integration(self):
        # 1 W (1000 mW) for 1 hour = 1 Wh, verifiable by hand.
        acc = EnergyAccumulator()
        first = acc.update({"pwr_mw": 1000}, ts=0.0)
        self.assertEqual(first.energy_wh, 0.0)  # no prior timestamp
        self.assertAlmostEqual(first.power_w, 1.0)

        second = acc.update({"pwr_mw": 1000}, ts=3600.0)
        self.assertAlmostEqual(second.energy_wh, 1.0)

        third = acc.update({"pwr_mw": 2000}, ts=7200.0)
        self.assertAlmostEqual(third.energy_wh, 3.0)  # 1 + 2

    def test_power_from_bus_voltage_and_current(self):
        acc = EnergyAccumulator()
        s = acc.update({"bus_v": 12.0, "current_ma": 250.0}, ts=0.0)
        self.assertAlmostEqual(s.power_w, 3.0)  # 12V * 0.25A

    def test_timestamp_regression_no_negative_energy(self):
        acc = EnergyAccumulator()
        acc.update({"pwr_mw": 1000}, ts=1000.0)
        s = acc.update({"pwr_mw": 1000}, ts=500.0)  # clock went backwards
        self.assertEqual(s.energy_wh, 0.0)  # must not go negative
        self.assertIn("timestamp_regression", s.quality_warnings)

    def test_large_interval_flag(self):
        acc = EnergyAccumulator(max_interval_s=3600.0)
        acc.update({"pwr_mw": 1000}, ts=0.0)
        s = acc.update({"pwr_mw": 1000}, ts=10000.0)  # 10000s gap
        self.assertIn("large_interval", s.quality_warnings)

    def test_no_warnings_on_normal_samples(self):
        acc = EnergyAccumulator(max_interval_s=3600.0)
        acc.update({"pwr_mw": 1000}, ts=0.0)
        s = acc.update({"pwr_mw": 1000}, ts=300.0)
        self.assertEqual(s.quality_warnings, ())


if __name__ == "__main__":
    unittest.main()
