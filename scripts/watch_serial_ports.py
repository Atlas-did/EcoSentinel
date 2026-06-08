"""Watch serial ports and report when ports appear/disappear.

Usage (PowerShell):
  .\.venv\Scripts\python.exe scripts\watch_serial_ports.py

Then plug/unplug the ESP32-S3 USB cable and observe changes.
Press Ctrl+C to stop.
"""

from __future__ import annotations

import time

try:
    from serial.tools import list_ports
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "pyserial is required. Install with: pip install pyserial\n"
        f"Import error: {exc}"
    )


def snapshot() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in list_ports.comports():
        desc = p.description or ""
        mfg = p.manufacturer or ""
        hwid = p.hwid or ""
        out[p.device] = f"{desc} | {mfg} | {hwid}".strip(" |")
    return out


def main() -> None:
    prev = snapshot()
    print("Watching serial ports. Plug/unplug your ESP32-S3 now...\n")
    if prev:
        print("Initial ports:")
        for dev, meta in sorted(prev.items()):
            print(f"  {dev}: {meta}")
        print("")
    else:
        print("Initial ports: (none)\n")

    while True:
        time.sleep(0.5)
        cur = snapshot()
        added = [d for d in cur.keys() if d not in prev]
        removed = [d for d in prev.keys() if d not in cur]

        if added or removed:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] change detected")
            for d in added:
                print(f"  + {d}: {cur[d]}")
            for d in removed:
                print(f"  - {d}: {prev[d]}")
            print("")
            prev = cur


if __name__ == "__main__":
    main()
