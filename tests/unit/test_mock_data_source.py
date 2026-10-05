"""mock 数据源的三条修复（评审 P1：mock 小时/室内温度/电参量）。

只用**可判定的性质**做断言，不去猜具体数值：
1) 传给 EnvironmentGenerator 的时间戳必须落在**本地**时刻（否则昼夜/在室率全反）
2) mock 的 temperature 必须是**室内量**（= 室外 + 内热稳态温差，温差由本仓参数推导）
3) 必须给出 bus_v / current_ma / pwr_mw，否则 EnergyAccumulator 永远累积不出 energy_wh
"""

import time
import unittest
from datetime import datetime
from unittest import mock

from energy_system.config import settings
from energy_system.core.data_acquisition import DataAcquisition


class _RecordingGenerator:
    """记录被传入的时间戳，并返回可预测的室外量与**固定小时**（便于分别测白天/夜间分支）。"""

    def __init__(self, t_out=30.0, solar=5.0, hour=12.0):
        self.seen = []
        self.t_out = t_out
        self.solar = solar
        self.hour = hour

    def now(self):
        return self.seen[-1] if self.seen else None

    def generate(self, t_s, use_random_walk=False):
        self.seen.append(t_s)
        return self.t_out, self.solar, self.hour

    def generate_humidity(self, t_s, use_random_walk=False):
        return 55.0


class TestMockDataSource(unittest.TestCase):
    def _acq(self, gen):
        return DataAcquisition(use_hardware=False, mock_generator=gen)

    def test_generator_receives_local_time_not_utc(self):
        gen = _RecordingGenerator()
        acq = self._acq(gen)
        acq.read()
        ts = gen.now()
        # 生成器内部就是用 (t_s/3600)%24 取小时的，因此这里也用同一公式验证：
        # 它取出来的小时必须等于本机当前**本地**小时（而不是 UTC 小时）。
        gen_hour = (ts / 3600.0) % 24.0
        local_now = datetime.now()
        local_hour = local_now.hour + local_now.minute / 60.0
        # 调用与断言之间可能跨过整点，故允许 1 分钟余量
        delta = abs(gen_hour - local_hour)
        delta = min(delta, 24.0 - delta) * 60.0
        self.assertLessEqual(delta, 1.5,
                             f"传给生成器的时间戳不是本地时刻（本地小时差 {delta:.1f} 分钟）")

    def test_mock_temperature_is_indoor_not_raw_outdoor(self):
        gen = _RecordingGenerator(t_out=30.0, hour=12.0)  # 固定白天分支
        sample = self._acq(gen).read()
        ua = settings.U_WALL * settings.A_WALL
        expected_delta = (settings.Q_PEOPLE + settings.Q_EQUIP) / ua
        self.assertGreater(expected_delta, 0.0, "本仓参数下白天内热温差应为正")
        self.assertNotAlmostEqual(sample["temperature"], 30.0, places=3,
                                  msg="mock 直接把室外温度当室内温度（评审 P1 第 1 条）")
        self.assertAlmostEqual(sample["temperature"], 30.0 + expected_delta, delta=0.06)

    def test_night_branch_uses_the_smaller_internal_gain(self):
        gen = _RecordingGenerator(t_out=30.0, hour=2.0)  # 固定夜间分支
        sample = self._acq(gen).read()
        ua = settings.U_WALL * settings.A_WALL
        self.assertAlmostEqual(sample["temperature"], 30.0 + 50.0 / ua, delta=0.06)

    def test_mock_provides_electrical_fields_for_energy_accounting(self):
        sample = self._acq(_RecordingGenerator()).read()
        for field in ("bus_v", "current_ma", "pwr_mw"):
            self.assertIn(field, sample, f"mock 缺 {field} ⇒ energy_wh 无法累积")
            self.assertGreater(float(sample[field]), 0.0)
        # 三者的内部一致性：pwr_mw 应等于 bus_v × current_ma（同单位换算后）
        derived_w = float(sample["bus_v"]) * float(sample["current_ma"]) / 1000.0
        self.assertAlmostEqual(derived_w, float(sample["pwr_mw"]) / 1000.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
