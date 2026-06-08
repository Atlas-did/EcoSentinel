from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Any


@dataclass
class WinProcess:
    pid: int
    name: str
    command_line: str
    creation_date: str | None = None


def _run_powershell_json(command: str) -> Any:
    """Run PowerShell and parse JSON output.

    Uses `ConvertTo-Json -Compress` to make parsing reliable.
    Returns Python object or None on failure.
    """
    try:
        cp = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if cp.returncode != 0:
            return None
        out = (cp.stdout or "").strip()
        if not out:
            return None
        return json.loads(out)
    except Exception:
        return None


def list_processes() -> list[WinProcess]:
    """List running processes with PID, Name, CommandLine, CreationDate."""
    obj = _run_powershell_json(
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,Name,CommandLine,CreationDate | "
        "ConvertTo-Json -Compress"
    )
    if not obj:
        return []

    # ConvertTo-Json returns either dict (single) or list (many)
    rows = obj if isinstance(obj, list) else [obj]
    procs: list[WinProcess] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        pid = r.get("ProcessId")
        name = r.get("Name")
        cmd = r.get("CommandLine")
        if not isinstance(pid, int) or not isinstance(name, str):
            continue
        procs.append(
            WinProcess(
                pid=pid,
                name=name,
                command_line=str(cmd or ""),
                creation_date=str(r.get("CreationDate") or "") or None,
            )
        )
    return procs


def find_port_contenders(port_name: str = "COM4") -> list[WinProcess]:
    """Heuristically find processes likely to contend for a COM port.

    Windows doesn't provide a simple built-in way to map COM port -> owning PID
    without Sysinternals. We instead surface the usual suspects so users can
    quickly stop them.
    """
    port_name = (port_name or "").strip().upper()
    keywords = [
        "streamlit run",
        "dashboard.py",
        "main.py",
        "sniff_serial.py",
        "watch_serial_ports.py",
        "list_serial_ports.py",
        "arduino",
        "arduino-cli",
        "serial monitor",
        "putty",
        "teraterm",
        "platformio",
        "esptool",
    ]

    suspects: list[WinProcess] = []
    for p in list_processes():
        hay = f"{p.name} {p.command_line}".lower()
        if port_name and port_name.lower() in hay:
            suspects.append(p)
            continue
        if any(k in hay for k in keywords):
            suspects.append(p)
            continue
    # stable order: PID ascending
    suspects.sort(key=lambda x: x.pid)
    return suspects


def stop_processes(pids: list[int]) -> bool:
    pids = [int(x) for x in pids if isinstance(x, int) or str(x).isdigit()]
    if not pids:
        return True

    pid_list = ",".join(str(x) for x in sorted(set(pids)))
    cmd = f"Stop-Process -Id {pid_list} -Force; 'ok' | ConvertTo-Json -Compress"
    obj = _run_powershell_json(cmd)
    return obj == "ok"


def _which_handle_exe() -> str | None:
    """Find handle.exe in PATH or common project locations."""
    # 1) PATH
    for name in ("handle.exe", "Handle.exe"):
        try:
            cp = subprocess.run(["where", name], capture_output=True, text=True, check=False)
            if cp.returncode == 0:
                p = (cp.stdout or "").splitlines()[0].strip()
                if p and os.path.exists(p):
                    return p
        except Exception:
            pass

    # 2) workspace-relative hints (optional)
    candidates = [
        os.path.join(os.getcwd(), "tools", "handle.exe"),
        os.path.join(os.getcwd(), "handle.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p

    # 3) pyserial bundled location (some environments place it under serial/tools/)
    try:
        import serial.tools  # type: ignore

        base = Path(serial.tools.__file__).resolve().parent
        for cand in (base / "handle.exe", base / "Handle.exe"):
            if cand.exists():
                return str(cand)
    except Exception:
        pass
    return None


def find_com_owner_via_handle(port_name: str) -> list[dict[str, Any]]:
    """Precisely find which PIDs hold an open handle to a COM port.

    Requires Sysinternals `handle.exe`.
    Returns rows: {pid, process, target}.
    """
    port_name = (port_name or "").strip().upper()
    if not port_name:
        return []

    handle_exe = _which_handle_exe()
    if not handle_exe:
        return []

    # Programs open COM ports as \\.\COMx
    query_terms = [f"\\\\.\\{port_name}", port_name]

    text_out = ""
    for term in query_terms:
        try:
            cp = subprocess.run(
                [handle_exe, "-nobanner", "-accepteula", term],
                capture_output=True,
                text=True,
                check=False,
            )
            # handle.exe uses non-zero codes for "no matching handles" sometimes; keep stdout anyway
            out = (cp.stdout or "") + "\n" + (cp.stderr or "")
            if out.strip():
                text_out = out
                # If we got actual matches, stop. Otherwise try next term.
                if "No matching handles" not in out:
                    break
        except Exception:
            continue

    if not text_out.strip():
        return []

    rows: list[dict[str, Any]] = []
    for raw in text_out.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Typical line:
        # python.exe pid: 1234 type: File  1A0: \\.\COM4
        if " pid:" not in line or " type:" not in line or ":" not in line:
            continue
        try:
            # process
            proc = line.split(" pid:", 1)[0].strip()
            rest = line.split(" pid:", 1)[1]
            pid_str = rest.split(" ", 1)[0].strip()
            pid = int(pid_str)
            # target after the last ': '
            target = line.rsplit(":", 1)[1].strip()
            if port_name not in target.upper():
                # Some systems show device path; still include if term query matched.
                pass
            rows.append({"pid": pid, "process": proc, "target": target})
        except Exception:
            continue

    # Dedup
    seen: set[tuple[int, str]] = set()
    uniq: list[dict[str, Any]] = []
    for r in rows:
        key = (int(r.get("pid") or 0), str(r.get("target") or ""))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    uniq.sort(key=lambda x: int(x.get("pid") or 0))
    return uniq
