"""当日电量摘要：跨重启累加（评审 P1：进程重启即清零）。

做法：在临时目录里把 cwd 切过去（实现用的是相对路径 `logs/`），
用**两个独立实例**模拟"重启前后两个进程"，断言第二次写入是在既有值上**累加**而非覆盖。

⚠️ 当前实现（每次用进程内累计量覆盖文件）必然失败 —— 故意先看着它红，再改实现。
"""

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from energy_system.core.log_manager import LogManager


class TestDailyEnergyAccumulation(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)
        self.label = "baseline"
        self.path = Path("logs") / f"daily_energy_{self.label}_{date.today().isoformat()}.json"

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def _write(self, load_wh, solar_wh=0.0):
        # 每个实例代表一个"新进程"
        LogManager(self.label).update_daily_energy(
            {"energy_wh": load_wh, "solar_energy_wh": solar_wh, "soc_percent": 80.0}
        )

    def _read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_second_process_accumulates_on_top_of_the_first(self):
        self._write(10.0)
        self.assertAlmostEqual(self._read()["load_energy_wh"], 10.0, places=3)

        self._write(4.0)  # 模拟重启后的新进程
        total = self._read()["load_energy_wh"]
        self.assertAlmostEqual(total, 14.0, places=3,
                               msg=f"重启后应累加为 14 Wh，实得 {total}（旧实现会覆盖成 4）")

    def test_solar_and_net_follow_the_same_accumulation(self):
        self._write(10.0, 3.0)
        self._write(5.0, 2.0)
        obj = self._read()
        self.assertAlmostEqual(obj["load_energy_wh"], 15.0, places=3)
        self.assertAlmostEqual(obj["solar_energy_wh"], 5.0, places=3)
        self.assertAlmostEqual(obj["net_energy_wh"], 10.0, places=3)

    def test_no_temporary_file_is_left_behind(self):
        self._write(7.0)
        leftovers = [p.name for p in Path("logs").iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [], f"原子写留下的临时文件未清理：{leftovers}")


if __name__ == "__main__":
    unittest.main()
