"""空动作对照组的门禁（《report-benchmarks.md》P0-2 / BOPTEST 的 baseline 范式）。

背景与**本仓的修正**（不能照抄 BOPTEST，必须写明）：
- BOPTEST 的空动作返回 `u={}`，模型自带 PI thermostat 接手 ⇒ "空动作 = 把控制权交还建筑本体"
  （`examples/python/controllers/baseline.py:29-31`）。
- 本仓 1R1C 模型**没有自带 thermostat** ⇒ `do_nothing` 只能是"空调与照明都不动作"，
  只保留不可控内热。`baseline`（全天 24 ℃ 定值）**已经**是"建筑默认控制器"，
  故**不再新增 `building_default`**（否则与 `baseline` 逐值相同，是冗余）。

参考 CSV：`tests/references/control_groups.csv`（跑一次、提交、之后当门禁；同 BOPTEST
`testing/utilities.py:302-304` 的做法）。本文件的期望值**同时内联**一份，这样即使 CSV 缺失
也能守住门禁（覆盖边界：只核对本项目三个模式的 7 个字段，不含逐轨迹比对）。
"""

import csv
import statistics
import unittest
from pathlib import Path

from energy_system.simulation.simulator import Simulator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE = PROJECT_ROOT / "tests" / "references" / "control_groups.csv"

#: 内联参考（2026-10-06 采集，3 天 / seed=42 / dt=300s）
EXPECTED = {
    "do_nothing": {"total_kwh": 13.05, "band_share": 0.256},
    "baseline": {"total_kwh": 199.10, "band_share": 0.417},
    "saving": {"total_kwh": 164.01, "band_share": 0.206},
}


def _measure(mode: str) -> dict:
    from energy_system.algorithms.comfort_eval import time_in_band_share

    history = Simulator(mode=mode, seed=42).run_simulation(days=3)
    return {
        "mode": mode,
        "total_kwh": history["total_kwh"],
        "band_share": time_in_band_share(history["T_in"]),
        "t_in_mean": statistics.mean(history["T_in"]),
    }


class TestControlGroups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {mode: _measure(mode) for mode in EXPECTED}

    def test_golden_per_mode(self):
        for mode, want in EXPECTED.items():
            got = self.rows[mode]
            self.assertAlmostEqual(got["total_kwh"], want["total_kwh"], delta=0.05, msg=f"{mode} 能耗漂移")
            self.assertAlmostEqual(got["band_share"], want["band_share"], delta=0.002, msg=f"{mode} 带内占比漂移")

    def test_do_nothing_is_far_cheaper_than_any_control(self):
        """空动作几乎不耗电 —— 所以"省电"本身不是成就，必须与舒适约束一起看。"""
        self.assertLess(self.rows["do_nothing"]["total_kwh"], 0.2 * self.rows["baseline"]["total_kwh"])

    def test_do_nothing_runs_hot(self):
        """它的代价是热：均值室温显著高于两个受控模式。"""
        self.assertGreater(self.rows["do_nothing"]["t_in_mean"], self.rows["baseline"]["t_in_mean"] + 2.0)
        self.assertGreater(self.rows["do_nothing"]["t_in_mean"], self.rows["saving"]["t_in_mean"] + 1.5)

    def test_saving_does_not_beat_do_nothing_on_band_share(self):
        """★ 如实钉死：按 IPMVP 带内占比，节能策略**并不比什么都不做更好**（20.6% vs 25.6%）。

        这条存在的意义是**防止把"带内占比"当成绩宣传** —— 当前策略的时段表（夜间 26–28 ℃）
        把它推到了舒适带之外；要改善就得改策略，而不是改口径。
        """
        self.assertLess(
            self.rows["saving"]["band_share"],
            self.rows["do_nothing"]["band_share"],
            "若此断言失败，说明策略已优于空动作 —— 那时应连同文档一起更新",
        )

    def test_reference_csv_matches_the_live_run(self):
        if not REFERENCE.exists():
            self.skipTest("参考 CSV 缺失（可跑 scripts/control_groups.py --write 生成）")
        with REFERENCE.open("r", encoding="utf-8-sig", newline="") as fh:
            rows = {row["mode"]: row for row in csv.DictReader(fh)}
        for mode, want in EXPECTED.items():
            self.assertIn(mode, rows, f"参考 CSV 缺 {mode} 行")
            self.assertAlmostEqual(float(rows[mode]["total_kwh"]), want["total_kwh"], delta=0.05)


if __name__ == "__main__":
    unittest.main()
