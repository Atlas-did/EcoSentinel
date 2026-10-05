"""M5/G5 · 串口协议契约：清单(protocol/eco_protocol.yaml) ⟷ 两侧源码。

为什么需要：固件与主机各自演进时，"字段名/单位/命令"任何一侧悄悄改了，另一端**不会报错**，
只会静默失配（例如固件发 `pwr_mw`(mW)，主机若按 W 读就会得到 1000 倍误差）。
本测试把清单当唯一真值，**两侧都对着它断言**：

- 固件侧：解析 protocol.h 的命令分发（`line == "X"` / `line.startsWith("X")`）与全部回复令牌
- 主机侧：`serial_bridge.py` 的逐行解析与消息分类**行为**（截断行/超长行/非 JSON/非法数字/未知字段）
- 换算一致性：清单里的 scale ⟷ `domain/telemetry.py` 的 WIRE_FIELDS ⟷ 实现（EnergyAccumulator）

只改一侧（例如把 mW 改成 W）⇒ 本文件变红。
"""

import json
import re
import unittest
from pathlib import Path

import yaml

from energy_system.domain import telemetry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "protocol" / "eco_protocol.yaml"
PROTOCOL_H = PROJECT_ROOT / "firmware" / "esp32_s3_competition" / "protocol.h"


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


def _firmware_text() -> str:
    """protocol.h 源码，但**去掉注释** —— 否则注释里举例写的 `line == "X"` 会被误当成真实分发。"""
    text = PROTOCOL_H.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _firmware_dispatchers():
    """返回 (exact 集合, prefix 集合)，从 protocol.h 的实际分发语句提取。"""
    text = _firmware_text()
    exact = set(re.findall(r'line\s*==\s*"([A-Z_0-9]+)"', text))
    prefix = set(re.findall(r'line\.startsWith\("([A-Z_0-9]+)"\)', text))
    return exact, prefix


def _firmware_reply_tokens():
    text = _firmware_text()
    ok = set(re.findall(r'replyOk\("([A-Z_0-9]+)"\)', text))
    err = set(re.findall(r'replyError\("([A-Z_0-9]+)"\)', text))
    return ok, err


class TestManifestAgainstFirmware(unittest.TestCase):
    def test_every_manifest_command_is_dispatched_by_the_firmware(self):
        exact, prefix = _firmware_dispatchers()
        missing = []
        for cmd in _manifest()["commands"]:
            name, match = cmd["name"], cmd["match"]
            if match == "exact":
                ok = name in exact
            else:
                ok = name in prefix
            if not ok:
                missing.append(f"{name}(match={match})")
        self.assertEqual(missing, [], "清单里的命令在固件中没有对应分发：" + ", ".join(missing))

    def test_every_firmware_dispatcher_is_in_the_manifest(self):
        exact, prefix = _firmware_dispatchers()
        declared = {c["name"] for c in _manifest()["commands"]}
        undeclared = sorted((exact | prefix) - declared)
        self.assertEqual(
            undeclared,
            [],
            "固件分发但清单没登记的命令（协议漂移或死分支）：" + ", ".join(undeclared),
        )

    def test_no_command_is_dispatched_by_both_forms(self):
        """同一命令不得同时有精确与前缀两种分发 —— 后者会变成永远走不到的死分支。

        （这正是我修过的真实缺陷：READ_SENSORS/GET_STATE/PINMAP/I2C_SCAN 原本由 `==` 处理，
        后来又被加了 startsWith 分支，导致后者永不可达。）
        """
        exact, prefix = _firmware_dispatchers()
        both = sorted(exact & prefix)
        self.assertEqual(both, [], "以下命令同时存在两种分发（后者是死代码）：" + ", ".join(both))

    def test_manifest_match_form_agrees_with_the_firmware(self):
        exact, prefix = _firmware_dispatchers()
        wrong = []
        for cmd in _manifest()["commands"]:
            name, match = cmd["name"], cmd["match"]
            actual = exact if name in exact else prefix
            if name not in actual:
                wrong.append(f"{name}: 清单说 {match}，固件里没有这种分发")
            elif (name in exact) != (match == "exact"):
                wrong.append(f"{name}: 清单说 {match}，固件实际是另一种写法")
        self.assertEqual(wrong, [], "清单与固件的分发写法不一致：" + "; ".join(wrong))

    def test_firmware_reply_tokens_match_the_manifest(self):
        ok_tokens, err_tokens = _firmware_reply_tokens()
        declared_ok, declared_err = set(), set()
        for cmd in _manifest()["commands"]:
            for entry in cmd.get("replies", []):
                kind, token = entry.split(":", 1)
                (declared_ok if kind == "ok" else declared_err).add(token)
        # 通用错误令牌（例如 UNKNOWN_CMD）不属于任何单条命令
        declared_err |= set(_manifest().get("error_tokens", []))
        self.assertEqual(sorted(ok_tokens - declared_ok), [], "固件的 ok 令牌未登记")
        self.assertEqual(sorted(declared_ok - ok_tokens), [], "清单登记的 ok 令牌固件里没有")
        self.assertEqual(sorted(err_tokens - declared_err), [], "固件的 error 令牌未登记")

    def test_unknown_command_token_is_declared(self):
        _ok, err = _firmware_reply_tokens()
        self.assertIn("UNKNOWN_CMD", err)
        self.assertIn("UNKNOWN_CMD", _manifest()["error_tokens"])


class TestSensorFrameContract(unittest.TestCase):
    def _firmware_sensor_keys(self) -> set[str]:
        text = _firmware_text()
        match = re.search(r"static void replySensorsJson\(\).*?\n\}", text, re.DOTALL)
        self.assertIsNotNone(match, "未找到 replySensorsJson")
        body = match.group(0)
        keys = set(re.findall(r'\\"([a-z][a-z0-9_]*)\\"', body))
        keys |= set(re.findall(r'jsonPrint[A-Za-z]*\("([a-z][a-z0-9_]*)"', body))
        return keys

    def test_firmware_frame_keys_match_the_manifest(self):
        declared = set(_manifest()["sensor_frame"])
        actual = self._firmware_sensor_keys()
        self.assertEqual(sorted(actual - declared), [], "固件帧里有清单未登记的字段")
        self.assertEqual(sorted(declared - actual), [], "清单登记了固件不发的字段")

    def test_manifest_conversions_match_the_telemetry_registry(self):
        """两侧各自登记了换算，必须一致 —— 这就是"改一端单位必红"的那条。"""
        manifest = _manifest()["sensor_frame"]
        for wire_key, spec in manifest.items():
            field = telemetry.wire_field(wire_key)
            if spec["scale"] == 1.0 and spec["canonical"] == wire_key:
                self.assertIsNone(field, f"{wire_key} 是同名/无换算字段，不该出现在 WIRE_FIELDS")
                continue
            self.assertIsNotNone(field, f"清单里的换算字段 {wire_key} 未登记进 WIRE_FIELDS")
            self.assertEqual(field.canonical, spec["canonical"])
            self.assertAlmostEqual(field.scale, spec["scale"], places=9)

    def test_manifest_canonical_keys_are_registered_metrics(self):
        for wire_key, spec in _manifest()["sensor_frame"].items():
            self.assertTrue(
                telemetry.is_known(spec["canonical"]),
                f"{wire_key} → {spec['canonical']} 不是已登记的规范指标",
            )

    def test_declared_scale_is_what_the_implementation_does(self):
        """清单说 mW→W 是 0.001，就让实现真的算一遍（不是比对字面量）。"""
        from energy_system.power.energy_accounting import EnergyAccumulator

        acc = EnergyAccumulator()
        for wire_key, raw, expected in (("pwr_mw", 1500.0, 1.5),):
            self.assertAlmostEqual(
                acc.estimate_power_w({wire_key: raw}), expected, places=6
            )


class TestHostParserBehaviour(unittest.TestCase):
    """主机侧解析/分类的真实行为（无需硬件）。"""

    def setUp(self):
        from energy_system.hardware import serial_bridge

        self.mod = serial_bridge
        self.max_bytes = _manifest()["transport"]["max_frame_bytes"]

    def test_valid_sensor_frame_is_parsed_and_classified_as_sensor(self):
        line = json.dumps({"temperature": 25.5, "humidity": 48.0, "pwr_mw": 1500})
        obj = self.mod.parse_sensor_line(line)
        self.assertIsInstance(obj, dict)
        self.assertEqual(self.mod._classify_message(obj), "sensor")

    def test_ack_frame_is_classified_as_ack_not_sensor(self):
        obj = self.mod.parse_sensor_line('{"ok":true,"msg":"RELAY_SET"}')
        self.assertEqual(self.mod._classify_message(obj), "ack")

    def test_truncated_line_is_rejected(self):
        self.assertIsNone(self.mod.parse_sensor_line('{"temperature": 25.5'))

    def test_non_json_noise_and_error_markers_are_rejected(self):
        for line in ("ESP32 Ready", "DHT_NAN", "", "   ", "[1,2,3]", "{}extra"):
            self.assertIsNone(self.mod.parse_sensor_line(line), f"应拒绝: {line!r}")

    def test_unknown_fields_are_tolerated_for_forward_compat(self):
        line = json.dumps({"temperature": 25.0, "brand_new_field": 7})
        obj = self.mod.parse_sensor_line(line)
        self.assertEqual(obj["brand_new_field"], 7, "未知字段应被保留而不是报错")

    def test_non_numeric_value_does_not_crash_the_parser(self):
        """固件可能发 "nan"/"ERR" 这类非数字：解析层必须活着，交由富化层兜底。"""
        line = '{"temperature":"nan","humidity":null,"pwr_mw":"oops"}'
        obj = self.mod.parse_sensor_line(line)
        self.assertIsInstance(obj, dict)

        from energy_system.application.enrichment import TelemetryEnrichmentService

        svc = TelemetryEnrichmentService()
        enriched = svc.enrich(obj)  # 不得抛异常
        self.assertIn("comfort_score", enriched)

    def test_over_long_frame_is_rejected(self):
        """超过 max_frame_bytes 的行必须被丢弃（此前主机侧没有任何上限）。"""
        padding = "x" * (self.max_bytes + 10)
        line = '{"temperature": 25.0, "pad": "' + padding + '"}'
        self.assertGreater(len(line), self.max_bytes)
        self.assertIsNone(self.mod.parse_sensor_line(line))

    def test_frame_just_under_the_limit_is_accepted(self):
        pad = "y" * (self.max_bytes - 40)
        line = '{"temperature": 25.0, "pad": "' + pad + '"}'
        self.assertLessEqual(len(line), self.max_bytes)
        self.assertIsInstance(self.mod.parse_sensor_line(line), dict)


if __name__ == "__main__":
    unittest.main()
