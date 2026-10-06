"""PMV/PPD 可选模块的门禁（审计提醒："别把 pythermalcomfort 硬塞进核心依赖"）。

钉住四件事：
1. **无该依赖时模块仍可导入**，且核心 `requirements.txt` **不含** `pythermalcomfort`；
2. 缺依赖时 `pmv_ppd()` **抛 RuntimeError 并给安装指引**，**不返回假数**；
3. 有依赖时返回值在物理合理范围内（用区间断言，不钉具体数字 —— 那是库版本相关，不是我们的口径）；
4. `pmv_band_share([]) == 0.0`，且它是"PMV ∈ ±0.5 的时间占比"，与 IPMVP 的
   `time_in_band_share`（温度带占比）是**两个不同指标**。

覆盖边界：本文件只验证接口与降级行为，不验证 PMV 数值的物理正确性（那由 pythermalcomfort 与
ISO 7730 负责）；无依赖环境下第 3 条会**跳过**。
"""

import unittest
from pathlib import Path

from energy_system.algorithms.pmv_optional import (
    PMV_AVAILABLE,
    pmv_band_share,
    pmv_ppd,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestPmvOptional(unittest.TestCase):
    def test_core_requirements_do_not_pin_pythermalcomfort(self):
        """审计点名：不能让它进核心依赖（否则只想跑 API/测试的人也被迫装 numpy/scipy）。"""
        text = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        self.assertNotIn("pythermalcomfort", text, "pythermalcomfort 必须保持为可选依赖")

    def test_module_imports_without_the_optional_dependency(self):
        self.assertIsInstance(PMV_AVAILABLE, bool)

    def test_missing_dependency_raises_instead_of_faking_a_number(self):
        if PMV_AVAILABLE:
            self.skipTest("本环境装了 pythermalcomfort ⇒ 走 test_available_path")
        with self.assertRaises(RuntimeError) as ctx:
            pmv_ppd(25.0)
        self.assertIn("pythermalcomfort", str(ctx.exception))
        self.assertIn("可选", str(ctx.exception))

    def test_available_path_returns_plausible_values(self):
        if not PMV_AVAILABLE:
            self.skipTest("未安装 pythermalcomfort ⇒ 走降级路径")
        out = pmv_ppd(25.0)
        self.assertGreaterEqual(out["pmv"], -3.0)
        self.assertLessEqual(out["pmv"], 3.0)
        self.assertGreaterEqual(out["ppd"], 0.0)
        self.assertLessEqual(out["ppd"], 100.0)
        self.assertIn("assumptions", out)
        self.assertIn("met", out["assumptions"])

    def test_empty_input_gives_zero_not_nan(self):
        self.assertEqual(pmv_band_share([]), 0.0)

    def test_band_share_is_distinct_from_temperature_band_share(self):
        """两个"占比"不是一回事：温度带 [23,26] 是 IPMVP 口径；PMV 带 ±0.5 是感热口径。"""
        from energy_system.algorithms.comfort_eval import time_in_band_share

        self.assertIsNot(time_in_band_share, pmv_band_share)
        if PMV_AVAILABLE:
            self.assertNotEqual(pmv_band_share([25.0]), time_in_band_share([25.0], low=25.0, high=25.0))


if __name__ == "__main__":
    unittest.main()
