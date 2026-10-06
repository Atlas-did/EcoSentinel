"""前馈控制律门禁（《docs/deep-audit-report.md》§1.5 + 第 5 章步 2 后半）。

覆盖边界：在**具名参数集**下验证控制律的稳定性与舒适口径；realistic 是**文献量级假设、非实测**，
因此本文件所有数字都必须与"realistic 假设"一起引用，**不得**当作实测结论。

★ 三条被钉住的事实（都来自真实仿真，3 天 / seed=42 / mode=saving）：
  1. 旧律 bangbang + realistic ⇒ 相邻 |ΔT|>3 K 占 **13.4%** ⇒ 深度核查的"无阻尼振荡"指控成立；
  2. 新律 feedforward + realistic ⇒ 该占比 **0.0%**、T_in∈[20.6, 27.5]、带内占比 **77.3%**；
  3. 新律放在 demo（现状）参数上**反而更差**（184.16 vs 164.01 kWh）⇒ "三项必须一起改"成立。
"""

import unittest

from energy_system.algorithms.comfort_eval import time_in_band_share
from energy_system.simulation.simulator import Simulator

REALISTIC = {"U_WALL": 1.0, "A_WALL": 150.0, "C_AIR": 430000.0}


def _run(law: str, params: dict | None, days: int = 3) -> dict:
    history = Simulator(mode="saving", seed=42, params=params, control_law=law).run_simulation(days=days)
    track = history["T_in"]
    deltas = [abs(b - a) for a, b in zip(track, track[1:])]
    return {
        "kwh": history["total_kwh"],
        "band": time_in_band_share(track),
        "t_min": min(track),
        "t_max": max(track),
        "jump_ratio": sum(1 for d in deltas if d > 3.0) / len(deltas),
        "max_jump": max(deltas),
    }


class TestFeedforwardControlLaw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ff_real = _run("feedforward", REALISTIC)
        cls.bb_real = _run("bangbang", REALISTIC)
        cls.ff_demo = _run("feedforward", None)

    def test_feedforward_is_stable_under_realistic_params(self):
        """验收：相邻 |ΔT|>3 K 占比 < 5%（实测 0.0%）。"""
        self.assertLess(self.ff_real["jump_ratio"], 0.05)
        self.assertLess(self.ff_real["max_jump"], 3.0)

    def test_feedforward_keeps_temperature_in_a_sane_range(self):
        """实测 [20.63, 27.51]；此处给宽松但真实的上界（不夸大"完全落在 [21,29]"）。"""
        self.assertGreater(self.ff_real["t_min"], 19.0)
        self.assertLess(self.ff_real["t_max"], 29.0)

    def test_feedforward_reaches_the_band_share_target_under_realistic_params(self):
        """带内占比 77.3%（> 70%）。⚠️ 这是 **realistic 假设** 下的数字，不是实测。"""
        self.assertAlmostEqual(self.ff_real["band"], 0.773, delta=0.005)
        self.assertGreater(self.ff_real["band"], 0.70)
        self.assertAlmostEqual(self.ff_real["kwh"], 60.19, delta=0.05)

    def test_old_law_oscillates_under_realistic_params(self):
        """★ 必要性证据：同一个 realistic 参数下，旧律的跳变占比 13.4%（深度核查指控成立）。"""
        self.assertGreater(self.bb_real["jump_ratio"], 0.10)
        self.assertGreater(self.bb_real["jump_ratio"], self.ff_real["jump_ratio"] * 10)

    def test_new_law_is_worse_on_the_current_demo_params(self):
        """★ "三项必须一起改"：新律在 demo 参数下耗电更高（184.16 vs 164.01 kWh）。"""
        self.assertGreater(self.ff_demo["kwh"], 164.01)
        self.assertAlmostEqual(self.ff_demo["kwh"], 184.16, delta=0.05)

    def test_default_path_is_untouched(self):
        """不带任何新参数时，能耗必须仍是钉死的 164.01 kWh（用户批准的边界）。"""
        default = Simulator(mode="saving", seed=42).run_simulation(days=3)
        self.assertAlmostEqual(default["total_kwh"], 164.01, delta=0.05)

    def test_unknown_control_law_raises(self):
        from energy_system.core.controller import RuleBasedController

        with self.assertRaises(ValueError):
            RuleBasedController(mode="saving", control_law="mpc")


if __name__ == "__main__":
    unittest.main()
