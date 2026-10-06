"""具名参数集与热惯性联合约束的门禁（《deep-audit-report.md》第 5 章步 1）。

覆盖边界：只校验**参数集自身的一致性**（默认未被改动、demo 必然不合格、realistic 合格、
未知名字报错、来源标注了"非实测"）；**不**校验物理正确性 —— realistic 是文献量级论证，不是实测。

★ 本文件把深度核查的核心指控写成**可执行的断言**：
   现状 demo 参数（UA=1800、C=25000）⇒ τ=13.9 s、θ=exp(-300/13.9)=4.2e-10 ⇒ **必然不满足 θ>0.9**。
   也就是说"本模型无热惯性"从此不是一句话，而是一条 CI 断言。
"""

import math
import unittest

from energy_system.config import settings
from energy_system.config.settings import (
    ACTIVE_PARAMETER_SET,
    PARAMETER_SETS,
    check_parameter_set,
    parameter_set,
)

#: 队友深度核查给出的候选值（C=3.6e5）—— 它**不满足他自己的门槛**，本文件专门把它钉住
TEAMMATE_PROPOSED_C_AIR = 360000.0


class TestParameterSets(unittest.TestCase):
    def test_default_set_is_untouched(self):
        """用户批准的边界：只新增 realism 场景，**默认值一个都不改**。"""
        self.assertEqual(ACTIVE_PARAMETER_SET, "demo")
        self.assertEqual(settings.U_WALL, PARAMETER_SETS["demo"]["U_WALL"])
        self.assertEqual(settings.A_WALL, PARAMETER_SETS["demo"]["A_WALL"])
        self.assertEqual(settings.C_AIR, PARAMETER_SETS["demo"]["C_AIR"])

    def test_demo_set_necessarily_fails_the_inertia_constraint(self):
        """现状参数在数学上不可能有热惯性 —— 这条断言就是那句指控的可执行形式。"""
        with self.assertRaises(ValueError) as ctx:
            check_parameter_set("demo")
        self.assertIn("热惯性不足", str(ctx.exception))
        tau_demo = settings.C_AIR / (settings.U_WALL * settings.A_WALL)
        self.assertLess(tau_demo, 20.0)
        self.assertLess(math.exp(-settings.TIME_STEP / tau_demo), 1e-9)

    def test_realistic_set_satisfies_the_joint_constraint(self):
        info = check_parameter_set("realistic")
        min_tau = settings.TIME_STEP / math.log(1.0 / 0.9)
        self.assertGreater(info["tau_s"], min_tau)
        self.assertGreater(info["theta"], 0.9)
        self.assertGreater(info["UA_w_per_k"], 50.0)   # 文献量级下限
        self.assertLessEqual(info["UA_w_per_k"], 150.0)  # 文献量级上限（本次取 150）

    def test_teammate_proposed_value_would_have_failed_his_own_gate(self):
        """C=3.6e5 配 UA=150 ⇒ τ=2400 s、θ=0.882 < 0.9 ⇒ 当场不达标（故我们改用不等式与 4.3e5）。"""
        tau = TEAMMATE_PROPOSED_C_AIR / 150.0
        theta = math.exp(-settings.TIME_STEP / tau)
        self.assertLess(theta, 0.9)
        self.assertAlmostEqual(tau, 2400.0, delta=1.0)

    def test_unknown_set_name_raises_instead_of_falling_back(self):
        with self.assertRaises(KeyError):
            parameter_set("does-not-exist")
        with self.assertRaises(KeyError):
            check_parameter_set("does-not-exist")

    def test_sources_declare_that_realistic_is_not_a_measurement(self):
        self.assertIn("非实测", PARAMETER_SETS["realistic"]["source"])
        self.assertIn("文献量级", PARAMETER_SETS["realistic"]["source"])
        self.assertIn("演示", PARAMETER_SETS["demo"]["source"])


if __name__ == "__main__":
    unittest.main()
