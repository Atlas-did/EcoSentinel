r"""Quickly verify ESP32 serial output.

Usage:
    .venv\Scripts\python.exe scripts\sniff_serial.py --port COM4 --baud 115200

Tips:
- Close Arduino Serial Monitor before running this.
- If your firmware prints only once at boot, start this script first,
    then press the board EN/RESET button to see the boot logs.
- If you see JSON lines, the PC side is ready.
"""

from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="Serial port, e.g. COM4")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=10.0)
    args = ap.parse_args()

    try:
        import serial  # type: ignore
    except Exception as exc:
        print("pyserial is required. Install with: pip install pyserial")
        print(f"Import error: {exc}")
        return 2

    deadline = time.time() + float(args.seconds)
    print(f"Opening {args.port} @ {args.baud} for {args.seconds:g}s...")
    print("Tip: if nothing prints, press EN/RESET once during capture.\n")

    try:
        with serial.Serial(args.port, args.baud, timeout=1) as ser:
            # Give device a moment after opening
            time.sleep(0.2)
            while time.time() < deadline:
                line = ser.readline()
                if not line:
                    continue
                try:
                    s = line.decode("utf-8", errors="replace").rstrip("\r\n")
                except Exception:
                    s = str(line)
                print(s)
    except serial.SerialException as exc:  # type: ignore[attr-defined]
        print(f"Failed to open serial port: {exc}")
        print("If Arduino Serial Monitor is open, close it and retry.")
        return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
