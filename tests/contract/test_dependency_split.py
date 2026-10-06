"""依赖分层契约：核心包必须保持"轻"（评审 §8 第 5 步）。

两条不变量：
1) 核心包 `energy_system/` 不得 import streamlit / pandas / matplotlib
   —— 它们只属于 4 个 Streamlit 视图文件；
2) `requirements.txt`（核心）不得含 streamlit，而 `requirements-dashboard.txt` 必须含它，
   否则"拆分"只是形式上的。

这样以后有人在核心链路里图省事 `import pandas`，CI 会立刻拦住并说明原因。
"""

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ONLY = ("streamlit", "pandas", "matplotlib")


class TestDependencySplit(unittest.TestCase):
    def test_core_package_does_not_import_dashboard_libraries(self):
        offenders = []
        for path in sorted((PROJECT_ROOT / "energy_system").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for lib in DASHBOARD_ONLY:
                if re.search(rf"^\s*(?:import|from)\s+{lib}\b", text, re.MULTILINE):
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)} -> {lib}")
        self.assertEqual(
            offenders,
            [],
            "核心包出现了仪表盘专用依赖（应放进 requirements-dashboard.txt）：" + "; ".join(offenders),
        )

    def test_core_requirements_stay_light_and_dashboard_has_the_heavy_ones(self):
        core = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
        dash_path = PROJECT_ROOT / "requirements-dashboard.txt"
        self.assertTrue(dash_path.exists(), "缺少 requirements-dashboard.txt（拆分未落地）")
        dash = dash_path.read_text(encoding="utf-8")

        for lib in DASHBOARD_ONLY:
            self.assertNotRegex(
                core, rf"(?m)^\s*{lib}[<>=]", f"核心 requirements.txt 不应再包含 {lib}"
            )
            self.assertRegex(
                dash, rf"(?m)^\s*{lib}[<>=]", f"{lib} 应出现在 requirements-dashboard.txt"
            )
        self.assertRegex(
            dash, r"(?m)^\s*-r\s+requirements\.txt", "仪表盘依赖应包含核心依赖（-r requirements.txt）"
        )


if __name__ == "__main__":
    unittest.main()
