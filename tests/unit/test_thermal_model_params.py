"""参数覆盖的门禁（《deep-audit-report.md》第 5 章步 2 的前半）。

覆盖边界：只验证"覆盖能到达模型、默认路径不变、非法覆盖报错"，以及**热惯性的行为差异**；
不评价参数本身的物理正确性（realistic 是文献量级论证，不是实测）。

★ 这条门禁的核心断言：**同一个 `step()` 在两组参数下的记忆保留率**。
   demo（UA=1800, C=25000）⇒ θ = exp(-300/13.9) ≈ 4.2e-10（一步即到稳态，无热惯性）
   realistic（UA=150, C=4.3e5）⇒ θ = exp(-300/2867) ≈ 0.90（保留 90% 记忆）
两个数都来自闭式解，因此这条断言既不依赖天气也不依赖控制器。
"""

import math
import unittest

from energy_system.config import settings
from energy_system.core.thermal_model import ThermalModel
from energy_system.simulation.simulator import Simulator

REALISTIC = {"U_WALL": 1.0, "A_WALL": 150.0, "C_AIR": 430000.0}


class TestThermalModelOverrides(unittest.TestCase):
    def test_default_construction_reads_settings_unchanged(self):
        model = ThermalModel()
        self.assertEqual(model.C_air, settings.C_AIR)
        self.assertEqual(model.U_wall, settings.U_WALL)
        self.assertEqual(model.A_wall, settings.A_WALL)
        self.assertEqual(model.dt, settings.TIME_STEP)

    def test_override_replaces_only_the_given_keys(self):
        model = ThermalModel(params={"C_AIR": 430000.0})
        self.assertEqual(model.C_air, 430000.0)
        self.assertEqual(model.U_wall, settings.U_WALL)   # 未覆盖的仍来自 settings

    @staticmethod
    def _retention(params: dict | None) -> float:
        """夜间、无太阳、无空调 ⇒ Q_const=50 W，T_inf 可闭式算出；返回一步后的记忆保留率。"""
        model = ThermalModel(params=params)
        t_out, t_old = 30.0, 20.0
        t_new, _ = model.step(t_old, t_out, 0.0, 23, 0.0, False)
        ua = model.U_wall * model.A_wall
        t_inf = t_out + 50.0 / ua
        return (t_new - t_inf) / (t_old - t_inf)

    def test_demo_parameters_have_no_inertia(self):
        """现状参数：一步就把初始条件抹掉（θ≈4e-10）—— 这就是"无热惯性"的可执行形式。"""
        self.assertLess(abs(self._retention(None)), 1e-6)

    def test_realistic_parameters_retain_memory(self):
        """realistic 参数：一步后仍保留 >85% 记忆 ⇒ 时序策略在原理上才有意义。"""
        retention = self._retention(REALISTIC)
        self.assertGreater(retention, 0.85)
        expected = math.exp(-settings.TIME_STEP / (430000.0 / 150.0))
        self.assertAlmostEqual(retention, expected, places=6)

    def test_simulator_passes_overrides_through(self):
        default_track = Simulator(mode="baseline", seed=42).run_simulation(days=1)["T_in"]
        realistic_track = Simulator(mode="baseline", seed=42, params=REALISTIC).run_simulation(days=1)["T_in"]
        self.assertEqual(len(default_track), len(realistic_track))
        self.assertNotEqual(default_track, realistic_track, "覆盖必须真的传进仿真循环")

    def test_inertia_makes_the_track_rougher_not_smoother(self):
        """★ 记录一个**我先猜错**的性质（实测校正）：

        我原以为"有热惯性 ⇒ 温度更平滑"，实测**相反** ——
        realistic（有惯性）σ=2.95 > demo（无惯性）σ=2.57。
        原因：无惯性时每步都精确贴到该步稳态（稳态序列本身是平滑的）；
        有惯性时温度**滞后于**稳态并随之摆动。故本条断言按实测方向写。
        """
        import statistics

        default_track = Simulator(mode="baseline", seed=42).run_simulation(days=1)["T_in"]
        realistic_track = Simulator(mode="baseline", seed=42, params=REALISTIC).run_simulation(days=1)["T_in"]
        self.assertGreater(
            statistics.pstdev(realistic_track), statistics.pstdev(default_track),
            "若此断言失败说明惯性方向已改变，应连同本注释一起更新",
        )

    def test_invalid_overrides_raise(self):
        with self.assertRaises(KeyError):
            ThermalModel(params={"NOT_A_PARAM": 1.0})
        with self.assertRaises(ValueError):
            ThermalModel(params={"C_AIR": 0.0})
        with self.assertRaises(ValueError):
            ThermalModel(params={"C_AIR": -5.0})


if __name__ == "__main__":
    unittest.main()
