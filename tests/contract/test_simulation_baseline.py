"""G2：仿真基线 **golden 断言** —— 把四个数字钉进 CI。

背景（审计指出，成立）：此前 CI 只跑 `compare` 并**看退出码**，数字可以随便漂。
`bd8cc35` 把碳减排从 13.87 改成 20.03（热模型积分器修复），CI 全程**无感**；
审计还实测过：把 `opt_temp` 26→27，舒适度 49.3%→50.8%、节能率与减碳全变，而只有一条无关用例变红。

本文件补上这条门禁：**仿真输出一旦漂移，CI 立刻红**。

## 这些数字从哪来（要改必须先读这段）

- 来自 `python -m energy_system.simulation.compare`（3 天、`seed=42`、300 s 步长，确定性）。
- 2026-10 热模型由**显式欧拉**改为**解析指数积分**后重算：旧值 81.48/57.18/29.8%/13.87 出自发散模型，
  **已作废**（详见 `docs/refactor-baseline.md`、`docs/pmv-ppd-study.md`）。
- 建筑参数（`A_WALL/U_WALL/C_AIR`）目前是**演示级、未标定**值 ⇒ 这些数字是"内部一致性基线"，
  **不是**实测节能量；对外表述必须带口径（IPMVP Option C，3 天仿真，未覆盖全工况）。

## 改动这些数字时的正确流程

1. 确认是**有意**改变模型/参数（而不是无意漂移）；
2. 同时更新：本文件、`docs/refactor-baseline.md`、README 的口径声明、`docs/handoff.md`；
3. 在提交信息里写明"为什么变、变了多少"。
"""

import unittest

from energy_system.simulation.compare import run_compare

#: 因变量 → (golden 值, 容差)。容差取"足以吸收浮点噪声、又足以抓住模型漂移"的量级：
#: 审计的 `opt_temp 26→27` 实验会让舒适度动 +1.5 个百分点 ⇒ 0.002 的容差必然报红。
GOLDEN = {
    "baseline_energy_kwh": (199.10, 0.05),
    "saving_energy_kwh": (164.01, 0.05),
    "energy_saved_kwh": (35.09, 0.05),
    "saving_rate_percent": (17.6, 0.05),
    "carbon_reduced_kg": (20.03, 0.05),
    "baseline_comfort_mean": (0.493, 0.002),
    "saving_comfort_mean": (0.491, 0.002),
}


class TestSimulationBaselineGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = run_compare()["results"]

    def test_every_golden_number_is_pinned(self):
        offenders = []
        for key, (want, tol) in GOLDEN.items():
            self.assertIn(key, self.results, f"compare 输出缺少 {key}")
            got = float(self.results[key])
            if abs(got - want) > tol:
                offenders.append(f"{key}: 期望 {want}±{tol}，实得 {got}")
        self.assertEqual(
            offenders,
            [],
            "仿真基线漂移（若是有意改动，请按本文件 docstring 的流程同步更新）："
            + "; ".join(offenders),
        )

    def test_saving_rate_matches_the_energy_ratio(self):
        """交叉校验：节能率必须与两个能耗值自洽（防"只改一个数字"的假更新）。"""
        r = self.results
        expected = (r["baseline_energy_kwh"] - r["saving_energy_kwh"]) / r["baseline_energy_kwh"] * 100.0
        self.assertAlmostEqual(r["saving_rate_percent"], expected, delta=0.05)
        self.assertAlmostEqual(r["energy_saved_kwh"], r["baseline_energy_kwh"] - r["saving_energy_kwh"], delta=0.05)


if __name__ == "__main__":
    unittest.main()
