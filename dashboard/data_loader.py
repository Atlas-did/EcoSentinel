"""Log data loading utilities for the Streamlit dashboard.

Provides efficient tail-reading of JSONL log files and daily energy summary parsing.
"""

import json
from pathlib import Path


def read_tail_jsonl(path: str | Path, max_rows: int = 120) -> list[dict]:
    """Read last N JSONL rows efficiently (best-effort).

    Reads from the end of the file in a single chunk, parses lines in reverse,
    and returns them in chronological order.
    """
    try:
        p = Path(path)
        if not p.exists() or p.stat().st_size <= 0:
            return []
        # Read last up to 256KB, then parse lines from bottom.
        with p.open("rb") as f:
            f.seek(0, 2)
            end = f.tell()
            read_size = min(262144, end)
            f.seek(end - read_size)
            chunk = f.read(read_size)
        text = chunk.decode("utf-8", errors="ignore")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        rows: list[dict] = []
        for ln in reversed(lines):
            if not (ln.startswith("{") and ln.endswith("}")):
                continue
            try:
                obj = json.loads(ln)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue
            if len(rows) >= int(max_rows):
                break
        return list(reversed(rows))
    except Exception:
        return []


def read_last_jsonl(path: str) -> dict | None:
    """Read only the last complete JSON object from a JSONL file."""
    try:
        p = Path(path)
        if not p.exists() or p.stat().st_size <= 0:
            return None
        with p.open("rb") as f:
            f.seek(0, 2)
            end = f.tell()
            read_size = min(65536, end)
            f.seek(end - read_size)
            chunk = f.read(read_size)
        text = chunk.decode("utf-8", errors="ignore")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in reversed(lines):
            if ln.startswith("{") and ln.endswith("}"):
                obj = json.loads(ln)
                return obj if isinstance(obj, dict) else None
    except Exception:
        return None
    return None


def estimate_channel_power_w(sample: dict, prefix: str = "") -> float | None:
    """Estimate power (W) from a sensor sample for a given channel prefix.

    Tries pwr_mw first (divides by 1000), then falls back to bus_v * current_ma / 1000.
    """
    pwr_mw = sample.get(f"{prefix}pwr_mw")
    if isinstance(pwr_mw, (int, float)):
        return float(pwr_mw) / 1000.0
    bus_v = sample.get(f"{prefix}bus_v")
    current_ma = sample.get(f"{prefix}current_ma")
    if isinstance(bus_v, (int, float)) and isinstance(current_ma, (int, float)):
        return float(bus_v) * float(current_ma) / 1000.0
    return None


def read_daily_summary(path: Path) -> dict | None:
    """Read a daily energy summary JSON file."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None
