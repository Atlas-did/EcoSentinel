r"""Hardware auto diagnosis for ESP32 competition firmware.

Usage:
  .venv\Scripts\python.exe scripts\hardware_autodiag.py --port COM4 --baud 115200

What it does:
1) Open serial and passively capture pushed JSON frames.
2) Send diagnostic commands (if firmware supports): PINMAP / I2C_SCAN / GET_STATE / READ_SENSORS.
3) Print a clear summary and wiring suggestions.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from dataclasses import field
from typing import Any


ESP32S3_INVALID = {22, 23, 24, 25}
ESP32S3_FLASH_OCCUPIED = {26, 27, 28, 29, 30, 31, 32}
ESP32S3_OCTAL_FLASH = {33, 34, 35, 36, 37}
ESP32S3_STRAPPING = {45, 46}
ESP32S3_USB_JTAG = {19, 20}


@dataclass
class DiagResult:
    pinmap: dict[str, Any] | None = None
    i2c_scan: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    sensor_sample: dict[str, Any] | None = None
    passive_samples: list[dict[str, Any]] = field(default_factory=list)


def parse_json_line(line: bytes) -> dict[str, Any] | None:
    s = line.decode("utf-8", errors="ignore").strip()
    if not s or not (s.startswith("{") and s.endswith("}")):
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def send_cmd_and_wait(ser, cmd: str, timeout_s: float = 1.8) -> list[dict[str, Any]]:
    ser.write((cmd + "\n").encode("utf-8"))
    end = time.time() + timeout_s
    out: list[dict[str, Any]] = []
    while time.time() < end:
        line = ser.readline()
        if not line:
            continue
        obj = parse_json_line(line)
        if obj is not None:
            out.append(obj)
    return out


def pick_latest(objs: list[dict[str, Any]], predicate) -> dict[str, Any] | None:
    for obj in reversed(objs):
        if predicate(obj):
            return obj
    return None


def validate_esp32s3_pin(pin: int, name: str) -> list[str]:
    warns: list[str] = []
    if pin in ESP32S3_INVALID:
        warns.append(f"🔴 {name}=GPIO{pin}：ESP32-S3 不存在此引脚")
    if pin in ESP32S3_FLASH_OCCUPIED:
        warns.append(f"🔴 {name}=GPIO{pin}：被内部 Quad SPI Flash/PSRAM 占用")
    if pin in ESP32S3_OCTAL_FLASH:
        warns.append(f"🔴 {name}=GPIO{pin}：被内部 Octal SPI Flash/PSRAM 占用")
    if pin in ESP32S3_STRAPPING:
        warns.append(f"⚠️ {name}=GPIO{pin}：Strapping 引脚，上电电平可能影响启动")
    if pin in ESP32S3_USB_JTAG:
        warns.append(f"⚠️ {name}=GPIO{pin}：默认 USB/JTAG 相关引脚，量产场景慎用")
    return warns


def validate_pinmap_for_esp32s3(pinmap: dict[str, Any]) -> tuple[list[str], list[str]]:
    fatal: list[str] = []
    soft: list[str] = []

    checks: list[tuple[Any, str]] = [
        (pinmap.get("i2c_sda"), "I2C_SDA"),
        (pinmap.get("i2c_scl"), "I2C_SCL"),
        (pinmap.get("dht"), "DHT"),
        (pinmap.get("buzzer"), "BUZZER"),
        (pinmap.get("ir_tx"), "IR_TX"),
    ]

    for idx, v in enumerate(pinmap.get("relay") or [], start=1):
        checks.append((v, f"RELAY_{idx}"))
    for idx, v in enumerate(pinmap.get("btn") or [], start=1):
        checks.append((v, f"BTN_{idx}"))
    for idx, v in enumerate(pinmap.get("stepper") or [], start=1):
        checks.append((v, f"STEPPER_{idx}"))

    tft = pinmap.get("tft")
    if isinstance(tft, dict):
        checks.extend(
            [
                (tft.get("miso"), "TFT_MISO"),
                (tft.get("mosi"), "TFT_MOSI"),
                (tft.get("sclk"), "TFT_SCLK"),
                (tft.get("cs"), "TFT_CS"),
                (tft.get("dc"), "TFT_DC"),
                (tft.get("rst"), "TFT_RST"),
                (tft.get("bl"), "TFT_BL"),
            ]
        )

    for pin, name in checks:
        if not isinstance(pin, int) or pin < 0:
            continue
        for msg in validate_esp32s3_pin(pin, name):
            if msg.startswith("🔴"):
                fatal.append(msg)
            else:
                soft.append(msg)

    return fatal, soft


def summarize(res: DiagResult) -> None:
    print("\n========== 诊断总结 ==========")
    fatal_pin_issues: list[str] = []

    if res.pinmap:
        print(f"[PINMAP] I2C = SDA {res.pinmap.get('i2c_sda')} / SCL {res.pinmap.get('i2c_scl')}")
        print(f"         IR_TX = {res.pinmap.get('ir_tx')} | ir_enabled = {res.pinmap.get('ir_enabled')}")
        if res.pinmap.get("warn_i2c_btn_conflict") is True:
            print("         ⚠️ I2C 与按键引脚复用冲突，请修改引脚定义。")

        fatal_pin_issues, soft_pin_issues = validate_pinmap_for_esp32s3(res.pinmap)
        for msg in fatal_pin_issues + soft_pin_issues:
            print(f"         {msg}")
    else:
        print("[PINMAP] 未获取（固件可能是旧版本，不支持 PINMAP 命令）")

    if res.i2c_scan:
        devs = res.i2c_scan.get("devices") or []
        print(f"[I2C_SCAN] devices = {devs}")
        print(
            "          BH1750(found)="
            f"{res.i2c_scan.get('bh1750_found')} INA219@0x40={res.i2c_scan.get('ina219_0x40_found')} "
            f"INA219@0x41={res.i2c_scan.get('ina219_0x41_found')} SGP30@0x58={res.i2c_scan.get('sgp30_0x58_found')}"
        )
    else:
        print("[I2C_SCAN] 未获取（固件可能是旧版本，不支持 I2C_SCAN 命令）")

    if res.state:
        print(
            f"[STATE] bh1750_ok={res.state.get('bh1750_ok')} "
            f"ina219_ok={res.state.get('ina219_ok')} sgp30_present={res.state.get('sgp30_present')} "
            f"i2c_recover_count={res.state.get('i2c_recover_count')}"
        )
        recover_count = res.state.get("i2c_recover_count")
        boot_count = res.state.get("boot_count")
        if isinstance(recover_count, (int, float)) and recover_count > 5:
            print(f"         ⚠️ I2C 自愈计数偏高(i2c_recover_count={recover_count})，可能存在总线不稳或引脚冲突。")
        if isinstance(boot_count, (int, float)) and boot_count > 50:
            print(f"         ⚠️ 设备重启次数偏高(boot_count={boot_count})，建议排查供电或异常重启。")

    sample = res.sensor_sample
    if sample:
        print(
            f"[SENSOR] illuminance={sample.get('illuminance')} temp={sample.get('temperature')} hum={sample.get('humidity')} "
            f"errors={sample.get('errors')}"
        )

    # Decision logic
    print("\n---------- 判定 ----------")

    if fatal_pin_issues:
        print("❌ 发现 ESP32-S3 引脚定义致命问题，后续 I2C 结论可能失真：")
        for msg in fatal_pin_issues:
            print(f"   - {msg}")
        print("   -> 请先修正固件引脚定义，再重新执行诊断。")
        print("\n---------- 建议（反幻觉） ----------")
        print("1) 先修 PINMAP 致命项，再看 I2C_SCAN/READ_SENSORS。")
        print("2) 诊断优先级：引脚合法性 > 接线 > 设备地址 > 传感器时序。")
        print("3) 如固件仍使用 GPIO22/23/26/33-37，请迁移到安全引脚后复测。")
        return

    bh_found = bool(res.i2c_scan and res.i2c_scan.get("bh1750_found") is True)
    lux_val = None if not sample else sample.get("illuminance")

    if bh_found and isinstance(lux_val, (int, float)):
        print("✅ BH1750 已识别且有光照读数。")
    elif bh_found and lux_val is None:
        print("⚠️ I2C 扫描能看到 BH1750，但 illuminance 为空：可能读时序/供电不稳，建议先发 I2C_RECOVER 再测试。")
    elif not bh_found:
        print("❌ I2C 总线未发现 BH1750 地址(0x23/0x5C)。优先检查 SDA/SCL 接线与供电。")

    print("\n---------- 建议（反幻觉） ----------")
    print("1) 以固件 PINMAP 为准，不要盲信表格。先确认固件实际 I2C 引脚。")
    print("2) 如果你把 I2C 接到 35/36，而固件是 21/22（或反之），BH1750 一定读不到。")
    print("3) IR 在当前固件是发送(TX)能力，不是“读数”传感器；未启用 USE_IR 时不会发送。")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="Serial port, e.g. COM4")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--passive-seconds", type=float, default=6.0)
    args = ap.parse_args()

    try:
        import serial  # type: ignore
    except Exception as exc:
        print(f"pyserial not installed: {exc}")
        return 2

    print(f"Opening {args.port} @ {args.baud} ...")
    res = DiagResult()

    try:
        with serial.Serial(args.port, args.baud, timeout=1) as ser:
            time.sleep(0.2)

            # Passive capture
            end = time.time() + float(args.passive_seconds)
            while time.time() < end:
                obj = parse_json_line(ser.readline())
                if obj is not None:
                    res.passive_samples.append(obj)

            if hasattr(ser, "reset_input_buffer"):
                ser.reset_input_buffer()

            # Active diagnostics
            objs: list[dict[str, Any]] = []
            per_cmd: dict[str, list[dict[str, Any]]] = {}
            for cmd in ("PINMAP", "I2C_SCAN", "GET_STATE", "READ_SENSORS"):
                got = send_cmd_and_wait(ser, cmd, timeout_s=1.6)
                per_cmd[cmd] = got
                objs.extend(got)

            all_objs = res.passive_samples + objs
            res.pinmap = pick_latest(per_cmd.get("PINMAP", []), lambda o: o.get("type") == "pinmap")
            if res.pinmap is None:
                res.pinmap = pick_latest(all_objs, lambda o: o.get("type") == "pinmap")

            res.i2c_scan = pick_latest(per_cmd.get("I2C_SCAN", []), lambda o: o.get("type") == "i2c_scan")
            if res.i2c_scan is None:
                res.i2c_scan = pick_latest(all_objs, lambda o: o.get("type") == "i2c_scan")

            res.state = pick_latest(per_cmd.get("GET_STATE", []), lambda o: o.get("type") == "state")
            if res.state is None:
                res.state = pick_latest(all_objs, lambda o: o.get("type") == "state")

            res.sensor_sample = pick_latest(
                per_cmd.get("READ_SENSORS", []) or all_objs,
                lambda o: any(k in o for k in ("illuminance", "temperature", "humidity", "relays")),
            )

            summarize(res)
            return 0

    except Exception as exc:
        print(f"Failed to open/read serial: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
