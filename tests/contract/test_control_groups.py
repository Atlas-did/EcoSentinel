"""对照矩阵门禁（含 **baseline 侧对照**）—— 用户任务 ①。

为什么必须补：saving 在 realistic+前馈下的 77.3% 带内占比，如果没有**同参同律**的 baseline 对照，
在 IPMVP 口径下站不住（"省了多少"必须相对一个明确的参照系）。

★ 本文件钉住三类事实：
  1. 三个模式在 **demo+bangbang**（= 现行口径）下的 golden —— 值必须与既有钉死数字一致；
  2. **配对对照**：demo+bangbang ⇒ 节能 17.62% 但带内占比 **−21.1 pt**（舒适代价）；
     realistic+feedforward ⇒ 节能 **32.80%** 且带内占比 **+17.4 pt**、越界 **−16.3 K·h**（两维同改善）；
  3. 空动作对照：demo 下 saving 的带内占比**劣于** do_nothing；realistic 下**优于**它。

覆盖边界：矩阵/配对数由 `scripts/control_groups.py` 生成、本文件按 `(mode, params, control_law)`
取值核对（容差见常量）；不评价参数集本身的物理（realistic 是**文献量级假设、非实测**）。
"""

import csv
import unittest
from pathlib import Path

from energy_system.simulation.simulator import Simulator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATRIX = PROJECT_ROOT / "tests" / "references" / "control_groups.csv"
PAIRED = PROJECT_ROOT / "tests" / "references" / "saving_vs_baseline.csv"

#: 现行口径（demo + bangbang）的三模式 golden，与 test_control_groups 的旧断言一致
DEMO_GOLDEN = {
    "do_nothing": (13.05, 0.2558),
    "baseline": (199.10, 0.4167),
    "saving": (164.012, 0.2060),
}
#: 配对对照 golden：(params, law) -> (节能率%, 带内占比Δ, 越界Δ K·h)
PAIRED_GOLDEN = {
    ("demo", "bangbang"): (17.62, -0.2107, 46.846),
    ("demo", "feedforward"): (15.86, -0.2512, 43.717),
    ("realistic", "bangbang"): (18.46, 0.0070, 50.290),
    ("realistic", "feedforward"): (32.80, 0.1736, -16.264),
}


def _read(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


class TestControlGroupMatrix(unittest.TestCase):
    def test_matrix_has_all_ten_cells(self):
        """3 模式 × 2 参数集 × 2 控制律，但 do_nothing 与控制律无关 ⇒ 10 行（不是 12）。"""
        rows = _read(MATRIX)
        self.assertEqual(len(rows), 10)
        keys = {(r["mode"], r["params"], r["control_law"]) for r in rows}
        for mode in ("baseline", "saving"):
            for params in ("demo", "realistic"):
                for law in ("bangbang", "feedforward"):
                    self.assertIn((mode, params, law), keys)
        for params in ("demo", "realistic"):
            self.assertIn(("do_nothing", params, "-"), keys)

    def test_demo_bangbang_column_matches_the_known_goldens(self):
        """现行口径那三个数不能漂：13.05 / 199.10 / 164.012 kWh 与带内占比 25.58/41.67/20.60%。"""
        rows = _read(MATRIX)
        got = {(r["mode"], r["params"], r["control_law"]): r for r in rows}
        for mode, (kwh, band) in DEMO_GOLDEN.items():
            law = "-" if mode == "do_nothing" else "bangbang"
            row = got[(mode, "demo", law)]
            self.assertAlmostEqual(float(row["total_kwh"]), kwh, delta=0.05, msg=f"{mode} 能耗漂移")
            self.assertAlmostEqual(float(row["band_share"]), band, delta=0.002, msg=f"{mode} 带内占比漂移")

    def test_paired_contrast_is_pinned(self):
        """★ IPMVP 口径真正需要的对照：每个 (params, law) 下 saving 相对同参同律 baseline 的差值。"""
        rows = _read(PAIRED)
        got = {(r["params"], r["control_law"]): r for r in rows}
        self.assertEqual(set(got), set(PAIRED_GOLDEN))
        for key, (rate, band_delta, viol_delta) in PAIRED_GOLDEN.items():
            row = got[key]
            self.assertAlmostEqual(float(row["saving_rate_percent"]), rate, delta=0.05, msg=f"{key} 节能率")
            self.assertAlmostEqual(float(row["band_share_delta"]), band_delta, delta=0.002, msg=f"{key} 带内占比差")
            self.assertAlmostEqual(float(row["temp_violation_delta_kh"]), viol_delta, delta=0.1, msg=f"{key} 越界差")

    def test_realistic_feedforward_improves_both_axes(self):
        """realistic+前馈是本项目第一次"节能且更舒适"：节能率>30% 且带内占比Δ>+15pt 且越界Δ<0。"""
        row = {(r["params"], r["control_law"]): r for r in _read(PAIRED)}[("realistic", "feedforward")]
        self.assertGreater(float(row["saving_rate_percent"]), 30.0)
        self.assertGreater(float(row["band_share_delta"]), 0.15)
        self.assertLess(float(row["temp_violation_delta_kh"]), 0.0)

    def test_current_口径_pays_a_comfort_cost(self):
        """现行口径（demo+bangbang）：带内占比 Δ 为负 —— 舒适代价必须被显式承认。"""
        row = {(r["params"], r["control_law"]): r for r in _read(PAIRED)}[("demo", "bangbang")]
        self.assertLess(float(row["band_share_delta"]), 0.0)
        self.assertGreater(float(row["temp_violation_delta_kh"]), 0.0)

    def test_saving_vs_do_nothing_per_control_law(self):
        """空动作对照（逐控制律，实测）：

        只有**现行口径 demo+bangbang** 劣于空动作（20.6% < 25.6%）；
        其余组合都优于它 —— demo+前馈 28.1%、realistic+bangbang 34.3%、realistic+前馈 77.3%（空动作仅 8.0%）。
        """
        rows = _read(MATRIX)
        by = {(r["params"], r["control_law"], r["mode"]): r for r in rows}
        expected = {
            ("demo", "bangbang"): False,       # 劣于空动作
            ("demo", "feedforward"): True,
            ("realistic", "bangbang"): True,
            ("realistic", "feedforward"): True,
        }
        for params in ("demo", "realistic"):
            base = float(by[(params, "-", "do_nothing")]["band_share"])
            for law in ("bangbang", "feedforward"):
                save = float(by[(params, law, "saving")]["band_share"])
                if expected[(params, law)]:
                    self.assertGreater(save, base, f"{params}+{law} 应优于空动作")
                else:
                    self.assertLess(save, base, f"{params}+{law} 应劣于空动作")

    def test_live_run_still_matches_the_current_口径(self):
        """与仿真连通：现行口径（无 params、无 control_law 参数）仍是 164.012 kWh。"""
        history = Simulator(mode="saving", seed=42).run_simulation(days=3)
        self.assertAlmostEqual(history["total_kwh"], 164.012, delta=0.05)


if __name__ == "__main__":
    unittest.main()
