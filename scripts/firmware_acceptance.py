"""ESP32 上板验收：读串口，判定固件自检令牌与必需子系统，给出**分级退出码**。

为什么需要它：没有令牌时，"板子通了没有"只能靠人眼看串口输出，无法自动判定，
也就没法交给同伴或 CI 一键验证。固件侧已在 setup() 末尾打印

    {"selftest":"pass","token":"ECO_SELFTEST_PASS","bh1750":true,...,"esp32_core":"3.3.7"}

（见 firmware/esp32_s3_competition/protocol.h 的 printSelfTest）

用法：
    python scripts/firmware_acceptance.py --port COM4
    python scripts/firmware_acceptance.py --port COM4 --require bh1750,relay --active

退出码（沿用仓库"退出码即事实"的风格）：
    0  PASS       收到 SELFTEST 令牌，且 --require 列出的子系统全部为 true
    1  NO_TOKEN   超时未收到令牌（固件没跑起来 / 串口接错 / 波特率不对）
    2  SUBSYSTEM  收到令牌但必需子系统缺失（打印缺失清单）
    3  PORT       串口打开失败（端口不存在或被占用）
    4  BAD_INPUT  --require 里出现未知的子系统名
"""

from __future__ import annotations

import argparse
import json
import sys

#: 固件自检令牌（与 protocol.h 的 printSelfTest 保持一致，改动需同步）
SELFTEST_TOKEN = "ECO_SELFTEST_PASS"

#: 固件会汇报的子系统键（--require 只能用这些）
KNOWN_KEYS = (
    "have_dht", "have_sgp30", "have_tft", "have_touch", "have_ina219",
    "bh1750", "sgp30", "ina219", "solar_ina219",
    "relay", "buzzer", "stepper",
)

EXIT_PASS, EXIT_NO_TOKEN, EXIT_SUBSYSTEM, EXIT_PORT, EXIT_BAD_INPUT = 0, 1, 2, 3, 4


def parse_json_line(line):
    """把一行文本解析成 dict；非 JSON / 非对象 / 截断行一律返回 None。

    固件同一条串口上既有 JSON 帧，也有 "ESP32 Ready" 这类纯文本行，
    所以解析必须是"尽力而为"而不是"假设每行都是 JSON"。
    """
    text = (line or "").strip()
    if not text.startswith("{"):
        return None
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def find_selftest(lines):
    """在若干行里找出自检负载；找不到返回 None。"""
    for line in lines:
        obj = parse_json_line(line)
        if obj and obj.get("token") == SELFTEST_TOKEN:
            return obj
    return None


def evaluate(payload, required):
    """判定自检负载是否满足必需子系统。返回 (ok, missing)。"""
    missing = []
    for key in required:
        if key not in KNOWN_KEYS:
            raise KeyError(key)
        if payload.get(key) is not True:
            missing.append(key)
    return (not missing), missing


def _print_payload(payload):
    print("  自检负载:")
    for key in ("boot", "i2c_recover", "esp32_core") + KNOWN_KEYS:
        if key in payload:
            print("    {:<14} {}".format(key, payload[key]))


def run(port, baud, timeout, required, active=False):
    """打开串口，等令牌，判定必需子系统。返回退出码。"""
    try:
        import serial  # 延迟导入：纯逻辑测试无需 pyserial
    except ImportError:
        print("  [ERR] 需要 pyserial：pip install pyserial")
        return EXIT_PORT

    try:
        ser = serial.Serial(port, baud, timeout=1)
    except Exception as exc:  # 端口不存在 / 被占用
        print("  [ERR] 打不开串口 {}: {}".format(port, exc))
        print("        检查：端口号是否正确、是否被 Arduino IDE 串口监视器占用。")
        return EXIT_PORT

    try:
        import time
        if active:
            ser.write(b"GET_STATE\n")
            print("  已发送 GET_STATE（验证命令通道双向可用）")

        deadline = time.time() + float(timeout)
        lines = []
        payload = None
        while time.time() < deadline:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue
            lines.append(line)
            obj = parse_json_line(line)
            if obj and obj.get("token") == SELFTEST_TOKEN:
                if active and not obj.get("ok", True):
                    continue
                payload = obj
                break
    finally:
        ser.close()

    if payload is None:
        print("  [FAIL] {} 秒内未收到自检令牌 {}".format(timeout, SELFTEST_TOKEN))
        print("        收到 {} 行，样例: {}".format(len(lines), lines[:3]))
        print("        检查：固件是否已烧录、波特率是否 {}、是否按了复位键。".format(baud))
        return EXIT_NO_TOKEN

    _print_payload(payload)
    ok, missing = evaluate(payload, required)
    if ok:
        print("  [PASS] 自检令牌已收到，必需子系统齐备: {}".format(", ".join(required) or "(未指定)"))
        return EXIT_PASS
    print("  [FAIL] 必需子系统缺失: {}".format(", ".join(missing)))
    print("        接线/供电检查参考 docs/hardware-guide.md；也可发 I2C_SCAN 自查总线。")
    return EXIT_SUBSYSTEM


def main(argv=None):
    parser = argparse.ArgumentParser(description="ESP32 上板验收（自检令牌 + 必需子系统）")
    parser.add_argument("--port", required=True, help="串口，如 COM4 或 /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=20.0, help="等待令牌的秒数")
    parser.add_argument("--require", default="bh1750",
                        help="必需的子系统，逗号分隔（默认 bh1750；可选: " + ", ".join(KNOWN_KEYS) + "）")
    parser.add_argument("--active", action="store_true",
                        help="额外发 GET_STATE 验证命令通道（需要固件支持）")
    args = parser.parse_args(argv)

    required = [k.strip() for k in args.require.split(",") if k.strip()]
    unknown = [k for k in required if k not in KNOWN_KEYS]
    if unknown:
        print("  [ERR] --require 含未知子系统: {}".format(", ".join(unknown)))
        print("        可用: {}".format(", ".join(KNOWN_KEYS)))
        return EXIT_BAD_INPUT

    print("ESP32 上板验收: port={} baud={} require={}".format(
        args.port, args.baud, required or "(无)"))
    return run(args.port, args.baud, args.timeout, required, active=args.active)


if __name__ == "__main__":
    sys.exit(main())
