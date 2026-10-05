"""M1/G8 · 指标注册表是单一真值，各语言的字段名必须与它一致。

检查四处（任何一处漂移都让 CI 变红，而不是线上字段对不上）：
1) 注册表自身（键唯一、有单位、kind 合法、别名指向已登记键）
2) Python API schema（`api/schemas.py` 的 Snapshot / ChartPoint 字段）
3) 固件 JSON（`firmware/esp32_s3_competition/protocol.h` 里打印的键）
4) 前端类型（`app/src/types/index.ts` 的 SensorSnapshot / ChartDataPoint）

说明：不是"遥测指标"的字段（如 ai_*、bridge_health、resilience）走下面的允许清单，
每条都要给出理由 —— 清单本身是文档，不是垃圾桶。
"""

import re
import unittest
from pathlib import Path

from energy_system.domain import telemetry
from energy_system.domain.telemetry import METRICS, MetricSpec

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_H = PROJECT_ROOT / "firmware" / "esp32_s3_competition" / "protocol.h"
TYPES_TS = PROJECT_ROOT / "app" / "src" / "types" / "index.ts"

#: 允许出现在 schema/接口里、但不属于遥测指标的字段 → 理由
NON_METRIC_ALLOWED = {
    "ai_reasoning": "AI 建议文本（AI 层输出，非遥测）",
    "ai_commands": "AI 建议命令（AI 层输出）",
    "ai_source": "AI 来源标记",
    "ai_candidate_id": "AI 候选标识",
    "ai_latency_ms": "AI 调用延迟（性能诊断）",
    "ai_score": "AI 评分",
    "ai_tuning_event": "AI 调参事件",
    "ai_cloud_error": "AI 云端错误",
    "ai_accepted_commands": "AI 通过校验的命令",
    "ai_rejected_commands": "AI 被拒命令",
    "ai_reject_reasons": "AI 拒绝原因",
    "bridge_health": "串口桥健康度（诊断）",
    "resilience": "自愈状态（诊断）",
    "accepted": "AI 候选的 UI 三态",
    "rejected": "AI 候选的 UI 三态",
    "rejectedReason": "AI 候选拒绝理由",
    "executed": "设备是否真的执行（契约语义，见 types/index.ts 注释）",
    "commands": "AI 候选携带的命令列表",
    "risk": "AI 候选风险标签",
    "createdAt": "AI 候选创建时间",
    "id": "候选/事件标识",
    "score": "AI 候选评分",
    "latency_ms": "AI 调用延迟",
    "incident_id": "自愈事件标识",
    "state": "自愈状态机取值",
    "last_action": "自愈最后动作",
    "last_action_reason": "自愈动作原因",
    "stale_detected": "自愈诊断",
    "retry_count": "自愈诊断",
    "sampling_rate_hz": "采样率（诊断）",
    "last_heartbeat": "心跳时间（诊断）",
    "self_healing_enabled": "自愈开关",
    "sensors_online": "传感器在线图（诊断）",
    "serial_connected": "串口连接状态（诊断）",
}


def _interface_fields(text: str, name: str) -> set[str]:
    """从 TS 源码里取 `export interface <name> { ... }` 的字段名。"""
    match = re.search(
        r"export interface " + name + r"\s*\{(?P<body>.*?)\n\}", text, re.DOTALL
    )
    if not match:
        raise AssertionError(f"未找到接口 {name}（types/index.ts 结构变了？）")
    fields = set()
    for line in match.group("body").splitlines():
        field = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\??\s*:", line)
        if field:
            fields.add(field.group(1))
    return fields


def _firmware_sensor_frame_keys() -> set[str]:
    """固件「传感器帧」(replySensorsJson) 里打印的键。

    只看这一个函数：protocol.h 还打印自检/PINMAP/I2C_SCAN 等诊断负载，
    那些不是遥测契约。键有两种写法：`Serial.print("\\"k\\":")` 与
    辅助函数参数 `jsonPrintFloatOrNull("k", ...)`，两种都要收。
    """
    text = PROTOCOL_H.read_text(encoding="utf-8")
    match = re.search(r"static void replySensorsJson\(\).*?\n\}", text, re.DOTALL)
    if not match:
        raise AssertionError("未找到 replySensorsJson（protocol.h 结构变了？）")
    body = match.group(0)
    keys = set(re.findall(r'\\"([a-z][a-z0-9_]*)\\"', body))
    keys |= set(re.findall(r'jsonPrint[A-Za-z]*\("([a-z][a-z0-9_]*)"', body))
    return keys


def _unregistered(fields: set[str]) -> set[str]:
    return {
        f
        for f in fields
        if not telemetry.is_known(f) and f not in NON_METRIC_ALLOWED
    }


class TestRegistrySelfConsistency(unittest.TestCase):
    def test_keys_are_unique_snake_case_with_units_and_valid_kind(self):
        for key, spec in METRICS.items():
            self.assertIsInstance(spec, MetricSpec)
            self.assertRegex(key, r"^[a-z][a-z0-9_]*$", f"键名不规范: {key}")
            self.assertTrue(spec.unit, f"{key} 缺单位")
            self.assertTrue(spec.description, f"{key} 缺说明")
            self.assertIn(spec.kind, {"sensor", "derived", "actuator", "state"})
            self.assertIn(spec.missing, {telemetry.MISSING_NAN, telemetry.MISSING_OMIT, telemetry.MISSING_ZERO})

    def test_aliases_point_at_registered_keys(self):
        for alias, target in telemetry.ALIASES.items():
            self.assertIn(target, METRICS, f"别名 {alias} 指向未登记的键 {target}")
            self.assertNotIn(alias, METRICS, f"别名 {alias} 不应同时是规范键")


class TestCrossLanguageAlignment(unittest.TestCase):
    def test_api_schema_fields_are_registered(self):
        from energy_system.api import schemas  # 延迟导入：仅此测试需要 FastAPI

        model = getattr(schemas, "Snapshot")
        fields = set(getattr(model, "model_fields", None) or model.__fields__)
        self.assertEqual(_unregistered(fields), set(), "API Snapshot 出现未登记字段")

    def test_api_chart_point_fields_are_registered(self):
        from energy_system.api import schemas

        model = getattr(schemas, "ChartPoint")
        fields = set(getattr(model, "model_fields", None) or model.__fields__)
        self.assertEqual(_unregistered(fields), set(), "API ChartPoint 出现未登记字段")

    def test_firmware_sensor_frame_keys_are_registered(self):
        keys = _firmware_sensor_frame_keys()
        self.assertIn("temperature", keys, "固件 JSON 解析失效（正则没匹配到键）")
        self.assertIn("pwr_mw", keys, "固件 JSON 解析失效（没收到毫瓦字段）")
        unknown = sorted(k for k in keys if not telemetry.is_known_wire(k))
        self.assertEqual(unknown, [], "固件传感器帧出现未登记的线上字段")

    def test_accumulator_defaults_and_scale_match_the_wire_registry(self):
        """注册表里写的映射必须与实现一致 —— 用可执行的方式验证，而不是只比字面量。"""
        import inspect

        from energy_system.power.energy_accounting import EnergyAccumulator

        params = inspect.signature(EnergyAccumulator.__init__).parameters
        for wire_key, param in (
            ("pwr_mw", "pwr_mw_key"),
            ("bus_v", "bus_v_key"),
            ("current_ma", "current_ma_key"),
        ):
            self.assertEqual(
                params[param].default, wire_key, f"累加器默认键 {param} 与线上登记不一致"
            )

        # 换算系数：注册表说 mW→W 是 0.001，就让实现真的算一遍
        acc = EnergyAccumulator()
        self.assertAlmostEqual(acc.estimate_power_w({"pwr_mw": 1500.0}), 1.5, places=6)
        solar = telemetry.wire_field("solar_pwr_mw")
        self.assertIsNotNone(solar)
        self.assertAlmostEqual(solar.scale, 0.001)

    def test_frontend_types_are_registered(self):
        text = TYPES_TS.read_text(encoding="utf-8")
        for interface in ("SensorSnapshot", "ChartDataPoint"):
            fields = _interface_fields(text, interface)
            self.assertTrue(fields, f"{interface} 未解析出字段")
            self.assertEqual(
                _unregistered(fields), set(), f"前端 {interface} 出现未登记字段"
            )


class TestWritePathGuards(unittest.TestCase):
    def test_set_metric_rejects_unregistered_key(self):
        data: dict = {}
        with self.assertRaises(KeyError):
            telemetry.set_metric(data, "comfort_scope", 1.0)  # 典型笔误

    def test_set_metric_normalizes_alias(self):
        data: dict = {}
        telemetry.set_metric(data, "temp", 25.0)
        self.assertEqual(data, {"temperature": 25.0})

    def test_unit_of_raises_for_unknown_metric(self):
        with self.assertRaises(KeyError):
            telemetry.unit_of("nope")


if __name__ == "__main__":
    unittest.main()
