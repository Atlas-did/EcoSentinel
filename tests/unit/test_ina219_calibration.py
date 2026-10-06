"""INA219 台架校正系数的门禁（队友第二轮审计指出的上板前必做项）。

背景：固件只调 `ina219.begin()`，**全文件无 `setCalibration`** ⇒ 用模块标称 0.4 Ω 分流电阻，
current/power 带 2–5% 系统误差。Adafruit 库的 `setCalibration(...)` 很可能是 protected，
故采用"读数出口乘实测比例"的软件校正。

本门禁钉住三件事：
1. **默认 1.0** ⇒ 与历史行为逐位一致（不得悄悄改默认值）；
2. 非 1.0 时只缩放 `current_ma` 与 `pwr_mw`，**`bus_v` 不动**；
3. 只作用于**硬件路径**，mock 生成器不参与校正。
"""

import unittest

from energy_system.core.data_acquisition import DataAcquisition


class _FakeBridge:
    def __init__(self, payload: dict):
        self.payload = payload

    def read_sensors(self) -> dict:
        return dict(self.payload)


SAMPLE = {"bus_v": 12.0, "current_ma": 1000.0, "pwr_mw": 12000.0, "temperature": 25.0}


class TestIna219Calibration(unittest.TestCase):
    def test_default_scale_is_unity(self):
        self.assertEqual(DataAcquisition.INA219_CURRENT_SCALE, 1.0)

    def test_unity_scale_returns_the_sample_unchanged(self):
        reader = DataAcquisition(use_hardware=True, serial_bridge=_FakeBridge(SAMPLE))
        self.assertEqual(reader.read(), SAMPLE)

    def test_scale_adjusts_current_and_power_but_not_voltage(self):
        original = DataAcquisition.INA219_CURRENT_SCALE
        DataAcquisition.INA219_CURRENT_SCALE = 1.25
        try:
            reader = DataAcquisition(use_hardware=True, serial_bridge=_FakeBridge(SAMPLE))
            out = reader.read()
        finally:
            DataAcquisition.INA219_CURRENT_SCALE = original
        self.assertEqual(out["current_ma"], 1250.0)
        self.assertEqual(out["pwr_mw"], 15000.0)
        self.assertEqual(out["bus_v"], 12.0, "电压不应被电流校正系数改动")
        self.assertEqual(out["temperature"], 25.0)

    def test_mock_path_is_not_calibrated(self):
        """mock 的电流/功率是模拟值 ⇒ 校正函数**不得被调用**（否则会改动仿真 golden）。

        注：不能靠"两次 mock 读数应相同"来判断 —— mock 是随机游走，值天然不同，那样会假红。
        这里直接侦测调用。
        """
        calls: list = []
        original = DataAcquisition._apply_ina219_calibration

        def spy(cls, data):  # noqa: ANN001
            calls.append(data)
            return original.__func__(cls, data)

        DataAcquisition._apply_ina219_calibration = classmethod(spy)
        try:
            DataAcquisition(use_hardware=False).read()
        finally:
            DataAcquisition._apply_ina219_calibration = original
        self.assertEqual(calls, [], "mock 路径不应经过 INA219 校正")

    def test_missing_bridge_returns_none(self):
        self.assertIsNone(DataAcquisition(use_hardware=True, serial_bridge=None).read())


if __name__ == "__main__":
    unittest.main()
