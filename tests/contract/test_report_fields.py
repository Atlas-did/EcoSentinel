"""报告字段契约：峰值/面积/code_version 必须存在且语义正确。

覆盖边界：只核对**字段存在性与语义自洽**（窗口时长、raw_max ≥ peak、code_version 格式），
不核对数值大小 —— 数值由 `test_peak_kpi.py`（口径）与 `test_simulation_baseline.py`（golden）负责。
"""

import re
import unittest

from energy_system.simulation.compare import run_compare

PEAK_FIELDS = (
    "baseline_peak_15min_kw",
    "saving_peak_15min_kw",
    "baseline_peak_raw_max_kw",
    "saving_peak_raw_max_kw",
    "peak_window_s",
    "baseline_peak_w_per_m2",
    "area_m2",
)


class TestReportFields(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_compare()

    def test_peak_and_area_fields_exist(self):
        for key in PEAK_FIELDS:
            self.assertIn(key, self.report["results"], f"报告缺少 {key}")

    def test_peak_window_is_fifteen_minutes(self):
        """窗口必须是 900 s —— 这是"需求侧计量窗口"的口径本身，不能被悄悄改小。"""
        self.assertEqual(self.report["results"]["peak_window_s"], 900.0)

    def test_windowed_peak_never_exceeds_raw_max(self):
        for prefix in ("baseline", "saving"):
            peak = self.report["results"][f"{prefix}_peak_15min_kw"]
            raw = self.report["results"][f"{prefix}_peak_raw_max_kw"]
            self.assertLessEqual(peak, raw + 1e-9, f"{prefix}: 窗口峰值不应大于单点最大")

    def test_area_is_present_but_only_for_reporting(self):
        self.assertEqual(self.report["results"]["area_m2"], 50.0)
        # 面积归一必须与 area 自洽（102 W/m² ≈ 5.1 kW / 50 m²）
        peak_w = self.report["results"]["baseline_peak_15min_kw"] * 1000.0
        self.assertAlmostEqual(
            self.report["results"]["baseline_peak_w_per_m2"], peak_w / 50.0, delta=0.5
        )

    def test_code_version_is_a_real_sha_or_explicitly_unknown(self):
        """**不许编造**：要么是 40 位十六进制 SHA，要么显式写 "unknown"。"""
        value = self.report["code_version"]
        self.assertTrue(
            value == "unknown" or re.fullmatch(r"[0-9a-f]{40}", value),
            f"code_version 既不是 SHA 也不是 unknown：{value!r}",
        )


if __name__ == "__main__":
    unittest.main()
