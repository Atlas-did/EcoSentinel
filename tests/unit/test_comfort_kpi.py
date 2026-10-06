"""舒适度越界积分（K·h）+ 分项的门禁。

钉住四件事（覆盖边界：**数学与区间语义**，不含"哪个区间更舒适"这类规范性判断 —— 那由
ISO 7730 / ASHRAE 55 与项目决策负责）：
1. 常数越界的积分**精确**等于"偏离量 × 时长"（梯形法端点只算一半）；
2. 区间内恒为 0；上下越界**同号**（都为正值）；
3. 单位与字段名一致（温度 K·h、湿度 %·h、照度 lx·h）；
4. 非法调用（区间反了、dt≤0）**抛错**而非静默返回 0。
"""

import unittest

from energy_system.algorithms.comfort_kpi import (
    TEMP_BAND_C,
    comfort_kpi_breakdown,
    violation_integral,
)


def _hour_of(value: float, dt_s: float = 300.0) -> list[float]:
    """返回恰好 1 小时、且每个采样点都等于 value 的序列（13 点 × 300 s = 3600 s）。"""
    return [value] * 13


class TestViolationIntegral(unittest.TestCase):
    def test_constant_violation_integrates_exactly(self):
        # 1 K 越界、持续 1 小时 ⇒ 恰好 1.0 K·h
        self.assertAlmostEqual(violation_integral(_hour_of(27.0), 23.0, 26.0), 1.0, places=9)
        self.assertAlmostEqual(violation_integral(_hour_of(22.0), 23.0, 26.0), 1.0, places=9)

    def test_two_kelvin_for_one_hour_is_two(self):
        self.assertAlmostEqual(violation_integral(_hour_of(28.0), 23.0, 26.0), 2.0, places=9)

    def test_in_band_is_zero(self):
        self.assertEqual(violation_integral(_hour_of(24.5), 23.0, 26.0), 0.0)
        self.assertEqual(violation_integral([23.0, 26.0], 23.0, 26.0), 0.0)

    def test_both_sides_are_positive(self):
        series = [22.0, 24.5, 27.0, 24.5]
        self.assertGreater(violation_integral(series, 23.0, 26.0), 0.0)

    def test_empty_and_missing_values_are_zero_not_nan(self):
        self.assertEqual(violation_integral([], 23.0, 26.0), 0.0)
        self.assertEqual(violation_integral([None, float("nan")], 23.0, 26.0), 0.0)
        self.assertEqual(violation_integral([25.0], 23.0, 26.0), 0.0)  # 单点无法积分

    def test_reversed_band_and_bad_dt_raise(self):
        with self.assertRaises(ValueError):
            violation_integral([25.0, 25.0], 26.0, 23.0)
        with self.assertRaises(ValueError):
            violation_integral([25.0, 25.0], 23.0, 26.0, dt_s=0.0)


class TestComfortKpiBreakdown(unittest.TestCase):
    def test_breakdown_reports_each_component_with_units_and_sources(self):
        out = comfort_kpi_breakdown(
            t_in=_hour_of(27.0),
            humidity=_hour_of(70.0),
            illuminance=_hour_of(50.0),
        )
        self.assertAlmostEqual(out["temp_violation_kh"], 1.0, places=6)
        self.assertAlmostEqual(out["humidity_violation_rh_h"], 10.0, places=6)   # 70 − 60 = 10 %·h
        self.assertAlmostEqual(out["illuminance_violation_lx_h"], 250.0 * 1.0, places=6)
        self.assertEqual(out["band_share"], 0.0)
        sources = out["assumptions"]
        self.assertEqual(sources["temp_band_c"], list(TEMP_BAND_C))
        self.assertIn("ISO 7730", sources["temp_band_source"])
        self.assertIn("ASHRAE", sources["rh_band_source"])
        self.assertIn("COMFORT_ILLUMINANCE_MIN", sources["lux_min_source"])

    def test_breakdown_omits_components_that_were_not_supplied(self):
        out = comfort_kpi_breakdown(t_in=_hour_of(24.0))
        self.assertIn("temp_violation_kh", out)
        self.assertNotIn("humidity_violation_rh_h", out)
        self.assertNotIn("illuminance_violation_lx_h", out)

    def test_band_share_agrees_with_the_standalone_metric(self):
        from energy_system.algorithms.comfort_eval import time_in_band_share

        series = [22.0, 24.0, 25.5, 27.0]
        out = comfort_kpi_breakdown(t_in=series)
        self.assertEqual(out["band_share"], round(time_in_band_share(series), 4))

    def test_real_simulation_produces_non_zero_violation(self):
        """与仿真连通性：3 天 baseline 必然有温度越界（室温区间远超 [23,26]）。"""
        from energy_system.simulation.simulator import Simulator

        history = Simulator(mode="baseline", seed=42).run_simulation(days=3)
        out = comfort_kpi_breakdown(t_in=history["T_in"], humidity=history["humidity"])
        self.assertGreater(out["temp_violation_kh"], 0.0)
        self.assertGreater(out["humidity_violation_rh_h"], 0.0)


if __name__ == "__main__":
    unittest.main()
