"""scripts/firmware_acceptance.py 的回归（无需硬件）。

除了纯逻辑，还包含两条**脚本 ↔ 固件的契约断言**：
- 固件里必须真的存在自检令牌字符串（否则脚本永远等不到）；
- 固件必须真的分发 GET_STATE / READ_SENSORS / PINMAP / I2C_SCAN
  （这四个回复函数此前**已实现却无人分发**，导致硬件自诊断脚本收不到应答）。
这样"文档说支持"与"固件真的支持"就不会再漂移。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.firmware_acceptance import (  # noqa: E402
    EXIT_BAD_INPUT,
    EXIT_NO_TOKEN,
    EXIT_PASS,
    EXIT_PORT,
    EXIT_SUBSYSTEM,
    KNOWN_KEYS,
    SELFTEST_TOKEN,
    evaluate,
    find_selftest,
    main,
    parse_json_line,
)

FIRMWARE_DIR = PROJECT_ROOT / "firmware" / "esp32_s3_competition"

GOOD = (
    '{"selftest":"pass","token":"ECO_SELFTEST_PASS","boot":3,"bh1750":true,'
    '"sgp30":false,"relay":true,"buzzer":true,"stepper":true}'
)


# ---------- 纯逻辑 ----------

def test_parse_json_line_accepts_json_object_only():
    assert parse_json_line(GOOD)["token"] == SELFTEST_TOKEN
    assert parse_json_line('  {"ok":true,"msg":"RELAY_OK"}  ')["ok"] is True


@pytest.mark.parametrize("line", [
    "ESP32 Ready",            # 固件启动横幅(纯文本)
    '{"token":"ECO_SELFTEST_PASS"',   # 截断行
    "[1,2,3]",               # JSON 但不是对象
    "", None, "   ",
])
def test_parse_json_line_rejects_non_objects_and_noise(line):
    assert parse_json_line(line) is None


def test_find_selftest_picks_token_among_noise():
    lines = ["ESP32 Ready", '{"ok":true,"msg":"BOOT"}', GOOD,
             '{"temperatureC":24.5,"humidityPct":50.0}']
    payload = find_selftest(lines)
    assert payload is not None and payload["boot"] == 3
    assert find_selftest(lines[:2]) is None


def test_evaluate_reports_missing_subsystems():
    payload = {"bh1750": True, "sgp30": False, "relay": True}
    assert evaluate(payload, ["bh1750", "relay"]) == (True, [])
    assert evaluate(payload, ["bh1750", "sgp30"]) == (False, ["sgp30"])
    # 缺失(键不存在)与显式 false 同判失败
    assert evaluate(payload, ["ina219"]) == (False, ["ina219"])


def test_evaluate_rejects_unknown_key():
    with pytest.raises(KeyError):
        evaluate({"bh1750": True}, ["not_a_subsystem"])


# ---------- 命令行行为（都不需要硬件） ----------

def test_unknown_require_is_bad_input(capsys):
    assert main(["--port", "COM1", "--require", "bh1750,nope"]) == EXIT_BAD_INPUT
    assert "未知子系统" in capsys.readouterr().out


def test_unopenable_port_returns_port_exit_code():
    # 不存在的端口：应给出 EXIT_PORT 而不是异常或误判为"没收到令牌"
    assert main(["--port", "COM_NOT_A_REAL_PORT_999", "--timeout", "0.2"]) == EXIT_PORT


# ---------- 脚本 ↔ 固件 契约 ----------

def test_firmware_still_defines_the_selftest_token():
    text = (FIRMWARE_DIR / "protocol.h").read_text(encoding="utf-8")
    assert SELFTEST_TOKEN in text, "固件缺少自检令牌，验收脚本将永远等不到"
    assert "printSelfTest" in text


def test_firmware_dispatches_the_diagnostic_commands():
    text = (FIRMWARE_DIR / "protocol.h").read_text(encoding="utf-8")
    for cmd in ("GET_STATE", "READ_SENSORS", "PINMAP", "I2C_SCAN", "SELFTEST"):
        # 固件两种分发写法都存在（精确匹配与前缀匹配）；此处只要求"有分发"，
        # "同一命令不得两种写法同时存在"由 tests/contract/test_serial_protocol.py 负责。
        dispatched = 'startsWith("{}")'.format(cmd) in text or '== "{}"'.format(cmd) in text
        assert dispatched, \
            "固件未分发 {}：回复函数存在但无人调用 ⇒ 自诊断/验收会静默失败".format(cmd)


def test_firmware_calls_selftest_in_setup():
    text = (FIRMWARE_DIR / "esp32_s3_competition.ino").read_text(encoding="utf-8")
    assert "printSelfTest();" in text, "setup() 未打印自检令牌"


def test_exit_codes_are_graded_and_distinct():
    codes = {EXIT_PASS, EXIT_NO_TOKEN, EXIT_SUBSYSTEM, EXIT_PORT, EXIT_BAD_INPUT}
    assert codes == {0, 1, 2, 3, 4}
    assert set(KNOWN_KEYS) == {
        "have_dht", "have_sgp30", "have_tft", "have_touch", "have_ina219",
        "bh1750", "sgp30", "ina219", "solar_ina219",
        "relay", "buzzer", "stepper",
    }


def test_optional_sensor_libs_have_explicit_enable_switches():
    """可选库不能只靠 __has_include —— 否则装了也永远编不进去。

    arduino-cli 只按预处理输出里出现的 #include 去 ResolveLibrary。库已安装
    时 __has_include 首轮仍为假 ⇒ #include 不出现 ⇒ 该库永远不被解析。
    实测：DHT/SGP30 库装好后编译，verbose 日志里从未出现两者的 ResolveLibrary。

    故每个可选库都必须有显式编译开关，且保留"不传开关时降级"的既有行为。
    """
    text = (FIRMWARE_DIR / "config.h").read_text(encoding="utf-8")
    for macro, header in (
        ("ECOSENTINEL_ENABLE_DHT", "DHT.h"),
        ("ECOSENTINEL_ENABLE_SGP30", "Adafruit_SGP30.h"),
    ):
        assert macro in text, (
            "%s 缺少显式开关 %s：库已安装时该传感器仍不会被编译进去" % (header, macro)
        )
        # 开关必须与 __has_include 并列为"或"关系，保证不传开关时行为不变
        pattern = "defined(%s) || __has_include(<%s>)" % (macro, header)
        assert pattern in text, (
            "%s 的保护写法必须是 `%s`（缺 BASELINE 降级会破坏 CI 路径）"
            % (header, pattern)
        )
        # 降级分支必须存在
        assert "#define HAVE_%s 0" % macro.rsplit("_", 1)[-1] in text

