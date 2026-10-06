"""ASO + IPMVP Option C 的门禁：调度正确性 / 报告自洽 / golden / 口径约束。

存在的理由（审计指出本项目曾有"数字可以随便漂"的缺口）：`aso_experiment` 是**新的估计量**，
一旦调度或回归被改坏，报告里的节能量会悄悄变，而 CI 只看退出码。这里把三件事钉住：

1. **调度**：逐日/逐块交替必须在正确的日子切换（否则"哪些天算 baseline"就错了）；
2. **自洽**：节能量 = 预测 baseline − 实测报告期；百分比 = 节能量/预测 baseline（防只改一个数字）；
3. **golden + 口径**：6 天/seed=42 的报告数字钉死；报告必须带"未覆盖全工况"这类口径说明，
   且 method 必须写明是 IPMVP Option C（不许悄悄换成别的估计量还叫同一个名字）。

注意：本文件的 golden 与 `test_simulation_baseline.py` 的 golden 是**两个不同估计量**
（配对差值 vs 回归外推），不要互相替换、不要取平均。
"""

import unittest

from energy_system.simulation.aso_experiment import (
    daily_alternating_schedule,
    run_aso_experiment,
)

SECONDS_PER_DAY = 24 * 3600


class TestAsoSchedule(unittest.TestCase):
    def test_daily_alternation_switches_on_the_right_days(self):
        sched = daily_alternating_schedule(1)
        self.assertEqual(sched(0), "baseline")                       # 第 0 天
        self.assertEqual(sched(12 * 3600), "baseline")               # 第 0 天中午
        self.assertEqual(sched(SECONDS_PER_DAY), "saving")           # 第 1 天
        self.assertEqual(sched(3 * SECONDS_PER_DAY), "saving")       # 第 3 天
        self.assertEqual(sched(4 * SECONDS_PER_DAY), "baseline")     # 第 4 天

    def test_block_period_alternates_every_n_days(self):
        sched = daily_alternating_schedule(2)
        self.assertEqual(sched(0), "baseline")
        self.assertEqual(sched(SECONDS_PER_DAY), "baseline")          # 第 1 天仍在同一块
        self.assertEqual(sched(2 * SECONDS_PER_DAY), "saving")        # 第 2 天换块
        self.assertEqual(sched(3 * SECONDS_PER_DAY), "saving")
        self.assertEqual(sched(4 * SECONDS_PER_DAY), "baseline")

    def test_rejects_non_positive_period(self):
        with self.assertRaises(ValueError):
            daily_alternating_schedule(0)


class TestAsoExperimentGolden(unittest.TestCase):
    """6 天 / seed=42 / 逐日交替的 golden（2026-10 采集）。"""

    @classmethod
    def setUpClass(cls):
        cls.report = run_aso_experiment(days=6, seed=42, period_days=1)

    def test_days_split_into_paired_periods(self):
        self.assertEqual(self.report["baseline_days"], 3)
        self.assertEqual(self.report["report_days"], 3)

    def test_golden_numbers(self):
        expected = {
            "predicted_baseline_kwh": (195.943, 0.05),
            "actual_report_kwh": (158.479, 0.05),
            "savings_kwh": (37.465, 0.05),
            "savings_percent": (19.12, 0.05),
            "savings_ci95_kwh": (4.212, 0.05),
        }
        offenders = [
            f"{key}: 期望 {want}±{tol}，实得 {self.report[key]}"
            for key, (want, tol) in expected.items()
            if abs(float(self.report[key]) - want) > tol
        ]
        self.assertEqual(offenders, [], "ASO 基线漂移（有意改动请同步本文件与文档口径）：" + "; ".join(offenders))

    def test_regression_fit_is_pinned(self):
        fit = self.report["regression"]
        self.assertAlmostEqual(fit["b"], 4.8101, delta=0.01)   # kWh/°C
        self.assertAlmostEqual(fit["a"], -74.7258, delta=0.05)
        self.assertAlmostEqual(fit["r2"], 0.8235, delta=0.001)
        self.assertEqual(int(fit["n"]), 3)

    def test_report_is_self_consistent(self):
        r = self.report
        self.assertAlmostEqual(r["savings_kwh"], r["predicted_baseline_kwh"] - r["actual_report_kwh"], delta=0.01)
        self.assertAlmostEqual(
            r["savings_percent"], r["savings_kwh"] / r["predicted_baseline_kwh"] * 100.0, delta=0.02
        )

    def test_report_states_the_method_and_the_caveat(self):
        """口径约束：必须写明 IPMVP Option C，且必须带"未覆盖全工况"的说明。"""
        self.assertIn("IPMVP Option C", self.report["method"])
        self.assertIn("未覆盖全工况", self.report["caveat"])

    def test_rejects_odd_day_counts(self):
        with self.assertRaises(ValueError):
            run_aso_experiment(days=5, seed=42)


class TestSimulatorBackwardCompatibility(unittest.TestCase):
    """不带调度时，Simulator 必须与改动前同语义（老 golden 另有一道门禁）。"""

    def test_without_schedule_all_steps_use_the_base_mode(self):
        from energy_system.simulation.simulator import Simulator

        h = Simulator(mode="baseline", seed=42).run_simulation(days=1)
        self.assertIn("mode", h, "history 必须记录 mode（供 ASO 聚合）")
        self.assertEqual(set(h["mode"]), {"baseline"})


if __name__ == "__main__":
    unittest.main()
