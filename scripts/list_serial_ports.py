r"""List available serial ports on this PC.

Usage (PowerShell):
  .\.venv\Scripts\python.exe scripts\list_serial_ports.py

This is the quickest way to confirm whether Windows has enumerated a COM port
for an ESP32-S3 board.
"""

from __future__ import annotations

try:
    from serial.tools import list_ports
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "pyserial is required. Install with: pip install pyserial\n"
        f"Import error: {exc}"
    )


def main() -> None:
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return

    print("Detected serial ports:\n")
    for p in ports:
        # p: ListPortInfo
        print(f"- device: {p.device}")
        if p.description:
            print(f"  desc:   {p.description}")
        if p.manufacturer:
            print(f"  mfg:    {p.manufacturer}")
        if p.hwid:
            print(f"  hwid:   {p.hwid}")
        if getattr(p, 'vid', None) is not None and getattr(p, 'pid', None) is not None:
            print(f"  vid:pid {p.vid:04x}:{p.pid:04x}")
        if p.serial_number:
            print(f"  sn:     {p.serial_number}")
        print("")


if __name__ == "__main__":
    main()
