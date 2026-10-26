"""G9 · 设备-围护匹配门禁（第二轮复验 §5 抓到的真问题 → CI 断言）。

背景：``settings.check_parameter_set`` 只守了**热惯性**（θ>0.9）。但复验实测两套参数在
**可控性**上反向失配：

    demo       UA=1800 → 制冷权限比 0.454、满制冷稳态 31.0 °C（目标 24 °C，**压不住**）
    realistic  UA=150  → 满制冷稳态 −12.7 °C（**一开就冻到冰点以下**，非物理）

⚠️ **修法方向**：复验报告建议"把 UA 抬到 ≥600"，本文件把那条**否掉** ——
600 W/K 不在真实单间 50–150 W/K 的量级内，那是拿一个约束换另一个约束。
真正的修法是**把设备选型配到围护上**：UA=150 时只需 ~1667 W 额定，而现值 3500 W 大了 2.1 倍。

覆盖边界：只校验**当前这两套参数集各自的匹配状况并如实记录**；
**不**断言"应该改成多少"（那需要实机标定，见 docs/hardware-runbook.md）。
"""

import math
import unittest

from energy_system.config import settings
from energy_system.config.settings import (
    MAX_COOLING_AUTHORITY,
    MIN_COOLING_AUTHORITY,
    PARAMETER_SETS,
    check_controllability,
    assert_controllable,
)


class TestControllabilityIsRecorded(unittest.TestCase):
    """把复验的实测数字钉成断言 —— 使"两套都不可用"成为可回归的事实陈述。"""

    def test_demo_is_cooling_authority_deficient(self):
        """demo：制冷权限不足，压不住 24 °C。"""
        info = check_controllability("demo")
        self.assertFalse(info["meets_controllability"])
        self.assertLess(info["cooling_authority_ratio"], MIN_COOLING_AUTHORITY)
        # 复验实测：需 23150 W，设备 10500 W，比值 0.454，满制冷稳态 31.0 °C
        self.assertAlmostEqual(info["required_cooling_w"], 23150.0, delta=5.0)
        self.assertAlmostEqual(info["cooling_authority_ratio"], 0.454, delta=0.005)
        self.assertAlmostEqual(info["t_inf_cool_c"], 31.03, delta=0.05)
        self.assertTrue(any("制冷权限不足" in v for v in info["violations"]))

    def test_realistic_is_cooling_authority_excessive(self):
        """realistic：设备相对房间过大 ⇒ 满制冷稳态越过冰点。"""
        info = check_controllability("realistic")
        self.assertFalse(info["meets_controllability"])
        self.assertLess(info["t_inf_cool_c"], 0.0, "满制冷稳态必须被记为非物理")
        self.assertAlmostEqual(info["t_inf_cool_c"], -12.67, delta=0.05)
        self.assertTrue(any("非物理" in v for v in info["violations"]))

    def test_the_two_sets_fail_in_opposite_directions(self):
        """★ 核心指控：不是"都偏大"或"都偏小"，而是**反向失配**。"""
        demo = check_controllability("demo")
        real = check_controllability("realistic")
        self.assertLess(
            demo["cooling_authority_ratio"],
            real["cooling_authority_ratio"],
            "demo 的制冷权限比应低于 realistic",
        )
        self.assertLess(demo["cooling_authority_ratio"], 1.0)
        self.assertGreater(real["cooling_authority_ratio"], 1.0)
        # demo 压不住 ⇒ 满制冷稳态高于目标；realistic 设备过大 ⇒ 稳态低于冰点。
        # 两者不是同一侧的偏差：demo 偏高、realistic 偏低。
        self.assertGreater(demo["t_inf_cool_c"], settings.T_SET_COMFORT_C)
        self.assertLess(real["t_inf_cool_c"], 0.0)

    def test_both_assert_controllable_raise(self):
        """两套都不该被当成"可用终点"—— assert_controllable 必须拒绝它们。"""
        for name in ("demo", "realistic"):
            with self.assertRaises(ValueError) as ctx:
                assert_controllable(name)
            self.assertIn("设备与围护不匹配", str(ctx.exception))

    def test_unknown_set_raises_instead_of_falling_back(self):
        with self.assertRaises(KeyError):
            check_controllability("does-not-exist")


class TestTheCorrectedRemedy(unittest.TestCase):
    """把"修法是配设备而不是抬 UA"钉成断言 —— 防止将来又被引导去改 U_WALL。"""

    def test_sizing_the_device_for_ua_150_is_enough(self):
        """UA=150 时所需冷量 5000 W ⇒ 额定 ~1667 W，现有 3500 W 设备大了 2.1 倍。"""
        ua = PARAMETER_SETS["realistic"]["U_WALL"] * PARAMETER_SETS["realistic"]["A_WALL"]
        required_cooling = settings.Q_AC_MAX * 0 + (  # 显式重算，避免被实现改动带着走
            ua * (settings.T_OUT_PEAK_C - settings.T_SET_COMFORT_C)
            + settings.Q_SOLAR_PEAK_W
            + settings.Q_INT_DAY_W
        )
        required_rated = required_cooling / settings.COP_COOLING
        self.assertAlmostEqual(required_cooling, 5000.0, delta=5.0)
        self.assertAlmostEqual(required_rated, 1667.0, delta=3.0)
        self.assertGreater(
            settings.Q_AC_MAX / required_rated, 2.0,
            "现有 Q_AC_MAX 相对 UA=150 所需应当明显过大（这才是不匹配的真因）",
        )

    def test_raising_ua_to_600_would_leave_the_realistic_range(self):
        """★ 这条必须**钉住 realistic 的实际 UA**，不能只写一句"600 > 150"。

        变异记录：初版这里只断言 `600.0 > 150.0`（恒真的废话），结果把
        `realistic.U_WALL` 从 1.0 改成 4.0（UA=600）时**门禁全绿** ⇒ 假绿。
        现在改为断言 realistic 的 UA **本身**落在真实量级区间内，
        于是任何把它抬出量级的改动都会立刻变红。
        """
        ua_realistic = (
            PARAMETER_SETS["realistic"]["U_WALL"] * PARAMETER_SETS["realistic"]["A_WALL"]
        )
        self.assertGreaterEqual(
            ua_realistic, 50.0, "realistic 的 UA 掉出真实单间下界 50 W/K"
        )
        self.assertLessEqual(
            ua_realistic, 150.0,
            "realistic 的 UA 超出真实单间上界 150 W/K —— "
            "这正是复验建议的 UA=600 修法的问题所在：它能过权限判据但脱离物理量级",
        )

    def test_demo_ua_is_outside_the_realistic_range_by_its_own_admission(self):
        """反过来钉住 demo：它自己承认是演示级，故不要求落在真实量级内 ——
        但**必须**仍然报"权限不足"，否则它的失配就没人知道了。"""
        ua_demo = PARAMETER_SETS["demo"]["U_WALL"] * PARAMETER_SETS["demo"]["A_WALL"]
        self.assertGreater(ua_demo, 150.0)
        self.assertLess(check_controllability("demo")["cooling_authority_ratio"], 1.0)

    def test_a_matched_device_would_satisfy_the_authority_band(self):
        """把 Q_AC_MAX 换成与 UA=150 匹配的额定值后，制冷权限落进 [1, MAX]。"""
        ua = PARAMETER_SETS["realistic"]["U_WALL"] * PARAMETER_SETS["realistic"]["A_WALL"]
        required_cooling = (
            ua * (settings.T_OUT_PEAK_C - settings.T_SET_COMFORT_C)
            + settings.Q_SOLAR_PEAK_W
            + settings.Q_INT_DAY_W
        )
        matched_rated = required_cooling / settings.COP_COOLING
        ratio = (matched_rated * settings.COP_COOLING) / required_cooling
        self.assertGreaterEqual(ratio, MIN_COOLING_AUTHORITY)
        self.assertLessEqual(ratio, MAX_COOLING_AUTHORITY)
        # 满制冷稳态应落在物理区间内，而不是冰点以下
        avail = matched_rated * settings.COP_COOLING
        t_inf = settings.T_OUT_PEAK_C + (
            settings.Q_SOLAR_PEAK_W + settings.Q_INT_DAY_W - avail
        ) / ua
        self.assertGreater(t_inf, 15.0, "匹配后的设备满制冷稳态应 >15 °C")
        self.assertLess(t_inf, settings.T_OUT_PEAK_C - 2.0)


class TestHeatingIsNotExercisedByThisWeather(unittest.TestCase):
    """诚实划界：天气生成器谷值 23 °C 离设定值只差 1 K，制热权限判据无意义。"""

    def test_heating_check_is_reported_as_not_exercised(self):
        info = check_controllability("realistic")
        self.assertFalse(
            info["heating_exercised"],
            "本项目的天气从不冷到需要制热 ⇒ 该判据必须标记为未触及，不能拿它当结论",
        )

    def test_weather_generator_minimum_is_mild(self):
        self.assertGreaterEqual(settings.T_OUT_MIN_C, settings.T_SET_COMFORT_C - 2.0)


if __name__ == "__main__":
    unittest.main()