"""舒适度口径门禁：IPMVP 原生"带内时间占比"。

为什么需要它（队友审计补充）：项目对外显示的"舒适度 49.3%"是**自定义 0–1 评分的均值**，
看起来像百分比却**不可与文献同表**；IPMVP Core Concepts 的原生 comfort 定义是
"percentage of time in comfort band"。本门禁钉住新口径的边界语义，防止悄悄改坏：

- 边界包含（23.0 / 26.0 计入带内）；
- 空输入 ⇒ 0.0（**不得**出现 NaN）；
- `None`/`NaN` 不计入分母；
- 带写反（low > high）必须**抛错**而不是静默返回 0。
"""

import unittest

from energy_system.algorithms.comfort_eval import (
    COMFORT_BAND_HIGH_C,
    COMFORT_BAND_LOW_C,
    time_in_band_share,
)


class TestTimeInBandShare(unittest.TestCase):
    def test_all_inside_is_one(self):
        self.assertEqual(time_in_band_share([24.0, 23.5, 25.9, 26.0]), 1.0)

    def test_none_inside_is_zero(self):
        self.assertEqual(time_in_band_share([20.0, 30.0, 22.9, 26.1]), 0.0)

    def test_half_inside_is_half(self):
        self.assertEqual(time_in_band_share([24.0, 30.0]), 0.5)

    def test_boundaries_are_inclusive(self):
        self.assertEqual(time_in_band_share([COMFORT_BAND_LOW_C]), 1.0)
        self.assertEqual(time_in_band_share([COMFORT_BAND_HIGH_C]), 1.0)
        self.assertEqual(time_in_band_share([COMFORT_BAND_LOW_C - 1e-9]), 0.0)

    def test_empty_and_missing_values_do_not_produce_nan(self):
        self.assertEqual(time_in_band_share([]), 0.0)
        self.assertFalse(time_in_band_share([]) != time_in_band_share([]))  # 不是 NaN
        # None / NaN 不计入分母：[24, None, 30] ⇒ 1/2
        self.assertEqual(time_in_band_share([24.0, None, 30.0]), 0.5)
        self.assertEqual(time_in_band_share([24.0, float("nan"), 30.0]), 0.5)
        self.assertEqual(time_in_band_share([None, float("nan")]), 0.0)

    def test_reversed_band_is_an_error_not_a_silent_zero(self):
        with self.assertRaises(ValueError) as ctx:
            time_in_band_share([24.0, 25.0], low=26.0, high=23.0)
        self.assertIn("反了", str(ctx.exception))

    def test_custom_band_is_honoured(self):
        self.assertEqual(time_in_band_share([25.0], low=25.0, high=25.0), 1.0)
        self.assertEqual(time_in_band_share([24.9], low=25.0, high=25.0), 0.0)


class TestComfortMetricsContrast(unittest.TestCase):
    """★ 两个口径的对照（2026-10 实测，队友审计促成的口径更正）。

    旧口径 `evaluate_comfort` 是 0–1 自定义评分，其温度项 `TCI` 在 24–28 ℃ 之外**恒为 0**，
    而湿度项均值高达 ≈0.956 ⇒ 它**几乎不随温度变化**，于是：
        旧口径  baseline 0.493 → saving 0.491   （差 −0.2 pt，看起来"没牺牲舒适"）
    换到 IPMVP 原生口径（带内时间占比）后真相相反：
        新口径  baseline 41.7% → saving 20.6%   （差 **−21.1 pt**，舒适时间腰斩）

    ⇒ README 原先那句"proving savings aren't from sacrificing comfort"**不成立**，已更正。
    本用例把这两个数钉死：口径再变、策略再改，都会在这里现形。
    """

    @classmethod
    def setUpClass(cls):
        from energy_system.simulation.simulator import Simulator

        cls.hist = {
            mode: Simulator(mode=mode, seed=42).run_simulation(days=3)
            for mode in ("baseline", "saving")
        }

    def _band_share(self, mode: str) -> float:
        return time_in_band_share(self.hist[mode]["T_in"])

    def test_ipmvp_band_share_golden(self):
        self.assertAlmostEqual(self._band_share("baseline"), 0.417, delta=0.002)
        self.assertAlmostEqual(self._band_share("saving"), 0.206, delta=0.002)

    def test_saving_mode_costs_a_large_share_of_comfort_time(self):
        """节能策略让"带内时间"少了约 21 个百分点 —— 这必须被显式承认，不能被旧口径掩盖。"""
        drop = self._band_share("baseline") - self._band_share("saving")
        self.assertGreater(drop, 0.15, f"带内时间下降 {drop:.1%}，应触发对外口径更正")

    def test_legacy_metric_is_blind_to_that_drop(self):
        """旧口径在这个对比里几乎不动（这正是它掩盖问题的证据，保留为反例）。"""
        import statistics

        from energy_system.algorithms.comfort_eval import evaluate_comfort

        legacy = {}
        for mode, h in self.hist.items():
            legacy[mode] = statistics.mean(
                evaluate_comfort(t, hh) for t, hh in zip(h["T_in"], h["humidity"])
            )
        self.assertAlmostEqual(legacy["baseline"], 0.493, delta=0.002)
        self.assertAlmostEqual(legacy["saving"], 0.491, delta=0.002)
        self.assertLess(abs(legacy["baseline"] - legacy["saving"]), 0.01)  # 旧口径"看不见"


if __name__ == "__main__":
    unittest.main()
