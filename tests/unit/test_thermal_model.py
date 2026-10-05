"""热模型：数学性质断言（评审 §2.1 / §2.5 的修复护栏）。

这些断言**只涉及数学性质**，不涉及"物理参数是否标定"（那是另一件事，见 docs/refactor-design-v1.md）：
以免把"某个参数应该取 45"这种需要公开来源的判断写进测试。

1) 一步推进必须与解析指数解一致 —— 显式欧拉在 dt=300s、τ=13.9s 时会给出 1e17 级别错误
2) 长程稳定：1 天 288 步必须全为有限值且落在物理可能的量级内
3) 稳态：常量输入下应收敛到 T_inf = (UA·T_out + Q_solar + Q_internal + Q_ac) / UA
4) 符号：is_heating=True 升温、False 降温（保留原符号分支，防止修复时改坏）
5) 空调可控性：最大制冷功率必须能把稳态拉到室外温度以下（否则模型没有控制意义）

⚠️ 当前实现（显式欧拉）**必然失败 1/2/3** —— 这是故意的：先看着它红，再改实现。
"""

import math
import unittest

from energy_system.config import settings
from energy_system.core.thermal_model import ThermalModel

STEPS_PER_DAY = int(24 * 3600 / settings.TIME_STEP)


def analytic_next_step(T0: float, T_out: float, I_solar: float, hour: int,
                       power_ac_w: float, is_heating: bool) -> float:
    """一阶线性 ODE 的精确解（供测试当参照物，不参与被测实现）。"""
    UA = settings.U_WALL * settings.A_WALL
    q_solar = settings.ALPHA_SOLAR * I_solar * settings.A_WINDOW
    q_internal = (settings.Q_PEOPLE + settings.Q_EQUIP) if 9 <= hour < 18 else 50.0
    q_ac = 0.0
    if power_ac_w > 0:
        q_ac = power_ac_w * settings.COP_HEATING if is_heating else -power_ac_w * settings.COP_COOLING
    t_inf = (UA * T_out + q_solar + q_internal + q_ac) / UA
    tau = settings.C_AIR / UA
    return t_inf + (T0 - t_inf) * math.exp(-settings.TIME_STEP / tau)


class TestThermalModelMath(unittest.TestCase):
    def setUp(self):
        self.model = ThermalModel()
        self.UA = settings.U_WALL * settings.A_WALL

    def test_one_step_matches_the_analytic_solution(self):
        """(1) 一步推进必须等于精确解 —— 显式欧拉在 dt>2τ 时不满足，会给出荒谬值。"""
        T0, T_out, I, hour, P = 24.0, 35.0, 400.0, 12, 1000.0
        got, _ = self.model.step(T0, T_out, I, hour, P, False)
        want = analytic_next_step(T0, T_out, I, hour, P, False)
        self.assertAlmostEqual(
            got, want, delta=1e-6 * max(1.0, abs(want)),
            msg=f"一步推进 {got:.3f}°C 与精确解 {want:.3f}°C 不符（显式欧拉不稳定？）",
        )

    def test_one_day_trajectory_stays_finite_and_plausible(self):
        """(2) 1 天轨迹必须有限且落在物理可能区间内。"""
        T = 24.0
        for _ in range(STEPS_PER_DAY):
            T, _ = self.model.step(T, 35.0, 300.0, 12, 800.0, False)
            self.assertTrue(math.isfinite(T), f"第 {_} 步出现非有限温度")
            self.assertGreater(T, -50.0, "温度低于物理可能下限（发散前兆）")
            self.assertLess(T, 80.0, "温度高于物理可能上限（发散前兆）")

    def test_converges_to_the_analytic_steady_state(self):
        """(3) 常量输入下应收敛到 T_inf（与 UA 的取值无关的恒等式）。"""
        T, T_out, I, hour, P = 24.0, 35.0, 300.0, 12, 1500.0
        for _ in range(200):
            T, _ = self.model.step(T, T_out, I, hour, P, False)
        q_solar = settings.ALPHA_SOLAR * I * settings.A_WINDOW
        q_internal = settings.Q_PEOPLE + settings.Q_EQUIP
        q_ac = -P * settings.COP_COOLING
        t_inf = (self.UA * T_out + q_solar + q_internal + q_ac) / self.UA
        self.assertAlmostEqual(T, t_inf, delta=0.5,
                               msg=f"未收敛到解析稳态 {t_inf:.2f}°C（实得 {T:.2f}°C）")

    def test_heating_and_cooling_signs_are_preserved(self):
        """(4) 符号分支：同一状态下 is_heating=True 必须比 False 更热（与参数取值无关）。"""
        same = (24.0, 35.0, 0.0, 12, 2000.0)
        t_heat, br_heat = self.model.step(*same, True)
        t_cool, br_cool = self.model.step(*same, False)
        self.assertGreater(br_heat["Q_ac"], 0.0, "制热时 Q_ac 应为正")
        self.assertLess(br_cool["Q_ac"], 0.0, "制冷时 Q_ac 应为负")
        self.assertGreater(t_heat, t_cool, "同一状态下制热必须比制冷更热（符号分支被改坏）")

    def test_default_parameters_give_the_ac_little_authority(self):
        """(5) 标记断言：记录**当前参数**下空调的真实控制能力（评审 P0#5 的量化证据）。

        UA = U_WALL·A_WALL = 1800 W/K，而 Q_AC_MAX·COP ≈ 1.05e4 W ⇒ 满功率只能拉低约 5.8 K。
        因此 35°C 室外 + 日照 + 内热时，满功率制冷也**压不到 30°C**。
        这不是数学缺陷，而是**参数标定问题**：修好积分后它仍然存在，需要**有公开来源的标定值**
        （评审建议 A_WALL=45 / U_WALL=1.5 / C_AIR=1.2e5，但本仓无可引用来源，故未擅自改值）。
        参数一旦被标定，本断言应当随之更新 —— 它是标记，不是"合格判据"。
        """
        T, T_out = 24.0, 35.0
        for _ in range(200):
            T, _ = self.model.step(T, T_out, 300.0, 12, settings.Q_AC_MAX, False)
        self.assertGreater(T, 30.0, f"满功率制冷后 {T:.1f}°C —— 若已标定参数，请更新本标记断言")
        self.assertLess(T, T_out, "即便参数偏大，满功率制冷也必须比室外更凉（否则模型无控制方向）")


if __name__ == "__main__":
    unittest.main()
