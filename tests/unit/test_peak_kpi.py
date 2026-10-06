"""峰值 KPI 的门禁（BOPTEST 的 15 分钟重采样范式）。

核心要守住的语义：**峰值 = 15 分钟窗口均值的最大值**，不是单点最大值。
单点最大值在 300 s 步长下是步长/求解器产物，不是电网冲击（BOPTEST kpi_calculator.py:404-406）。

覆盖边界：只验证"窗口均值 → max"这一步与面积归一；不验证配电容量/需量计口径（那需要真实计量与费率）。
"""

import unittest

from energy_system.algorithms.peak_kpi import (
    peak_power_15min_kw,
    peak_power_15min_kw_from_settings,
)


class TestPeakPower15Min(unittest.TestCase):
    def test_constant_series(self):
        out = peak_power_15min_kw([1000.0] * 30)
        self.assertAlmostEqual(out["peak_kw"], 1.0, places=6)
        self.assertAlmostEqual(out["raw_max_kw"], 1.0, places=6)

    def test_a_single_spike_is_damped_by_the_window(self):
        """★ 核心语义：单点尖峰被 15 分钟窗口平均掉。

        dt=300s ⇒ 每窗口 3 个点。基线 1 kW，每窗口第 1 点插一个 10 kW 尖峰：
          窗口均值 = (10 + 1 + 1)/3 = 4 kW   ← 峰值口径
          单点最大 = 10 kW                    ← 原始口径（并列报告，不偷偷替换）
        """
        series = []
        for _ in range(4):
            series.extend([10000.0, 1000.0, 1000.0])
        out = peak_power_15min_kw(series, dt_s=300.0)
        self.assertAlmostEqual(out["peak_kw"], 4.0, places=6)
        self.assertAlmostEqual(out["raw_max_kw"], 10.0, places=6)
        self.assertLess(out["peak_kw"], out["raw_max_kw"] / 2.0)

    def test_window_is_a_time_window_not_a_point_count(self):
        """窗口是**时间**窗口：dt 变化时每窗口的点数随之变化，峰值仍按 15 min 聚合。"""
        series = [2000.0] * 12
        out_300 = peak_power_15min_kw(series, dt_s=300.0)   # 每窗口 3 点
        out_60 = peak_power_15min_kw(series, dt_s=60.0)     # 每窗口 15 点
        self.assertAlmostEqual(out_300["peak_kw"], 2.0, places=6)
        self.assertAlmostEqual(out_60["peak_kw"], 2.0, places=6)

    def test_area_normalization_is_optional_and_honest(self):
        series = [1000.0] * 3
        self.assertIsNone(peak_power_15min_kw(series)["peak_w_per_m2"])
        self.assertAlmostEqual(peak_power_15min_kw(series, area_m2=50.0)["peak_w_per_m2"], 20.0, places=3)

    def test_settings_provide_the_area(self):
        out = peak_power_15min_kw_from_settings([1000.0] * 3)
        self.assertIsNotNone(out["peak_w_per_m2"], "settings.FLOOR_AREA_M2 应已声明（来源：本文件既有 50m² 假设）")

    def test_empty_and_missing_values(self):
        out = peak_power_15min_kw([])
        self.assertEqual(out["peak_kw"], 0.0)
        self.assertIsNone(out["peak_w_per_m2"])
        self.assertEqual(peak_power_15min_kw([None, float("nan")])["peak_kw"], 0.0)

    def test_invalid_inputs_raise(self):
        with self.assertRaises(ValueError):
            peak_power_15min_kw([1.0, 2.0], dt_s=0.0)
        with self.assertRaises(ValueError):
            peak_power_15min_kw([1.0, 2.0], dt_s=900.0, window_s=300.0)
        with self.assertRaises(ValueError):
            peak_power_15min_kw([1.0, 2.0], area_m2=0.0)

    def test_real_simulation_peak(self):
        from energy_system.simulation.simulator import Simulator

        history = Simulator(mode="saving", seed=42).run_simulation(days=1)
        out = peak_power_15min_kw_from_settings(history["power_total"])
        self.assertGreater(out["peak_kw"], 0.0)
        self.assertLessEqual(out["peak_kw"], out["raw_max_kw"])


if __name__ == "__main__":
    unittest.main()
