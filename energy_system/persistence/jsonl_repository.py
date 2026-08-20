"""JSONL telemetry repository.

The single place that reads log files for the API and dashboard. It tracks
corrupt lines explicitly (instead of silently swallowing them) so the health
endpoint can report data quality, and it filters by timestamp rather than by
row count when a time window is requested.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class JsonlReadResult:
    rows: list[dict]
    corrupt_records: int = 0


def _parse_ts(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


class JsonlTelemetryRepository:
    def __init__(self, log_dir: str | Path, run_label: str = "saving"):
        self.log_dir = Path(log_dir)
        self.run_label = run_label

    def _path(self, label: str | None, kind: str = "hardware") -> Path:
        label = label or self.run_label
        return self.log_dir / f"{kind}_{label}.jsonl"

    def has_log(self, label: str | None = None, kind: str = "hardware") -> bool:
        return self._path(label, kind).exists()

    def read_all(self, label: str | None = None) -> JsonlReadResult:
        """Read every valid record, counting corrupt lines."""
        path = self._path(label)
        rows: list[dict] = []
        corrupt = 0
        if not path.exists():
            return JsonlReadResult(rows=rows, corrupt_records=0)

        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            rows.append(obj)
                        else:
                            corrupt += 1
                    except json.JSONDecodeError:
                        corrupt += 1
        except OSError:
            # Permission error / concurrent truncation: surface as empty, not crash.
            return JsonlReadResult(rows=rows, corrupt_records=corrupt)

        return JsonlReadResult(rows=rows, corrupt_records=corrupt)

    def latest(self, label: str | None = None) -> dict | None:
        result = self.read_all(label)
        return result.rows[-1] if result.rows else None

    def tail(self, n: int = 200, label: str | None = None) -> JsonlReadResult:
        result = self.read_all(label)
        result = JsonlReadResult(
            rows=result.rows[-n:] if n > 0 and len(result.rows) > n else result.rows,
            corrupt_records=result.corrupt_records,
        )
        return result

    def read_since(self, window_s: float, label: str | None = None) -> JsonlReadResult:
        """Return records whose timestamp is within the last ``window_s`` seconds."""
        result = self.read_all(label)
        if window_s is None:
            return result

        now = datetime.now()
        cutoff = now - timedelta(seconds=float(window_s))
        rows: list[dict] = []
        for row in result.rows:
            ts = _parse_ts(row.get("timestamp"))
            if ts is None or ts >= cutoff:
                rows.append(row)
        return JsonlReadResult(rows=rows, corrupt_records=result.corrupt_records)

    def daily_summary(self, label: str | None = None) -> dict | None:
        """Read today's daily energy summary JSON, if present."""
        from datetime import date

        label = label or self.run_label
        path = self.log_dir / f"daily_energy_{label}_{date.today().isoformat()}.json"
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return None

    def incident_tail(self, n: int = 50, label: str | None = None) -> list[dict]:
        # incidents are stored in a separate file; read that directly.
        path = self._path(label, kind="incidents")
        rows: list[dict] = []
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            rows.append(obj)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return rows[-n:] if len(rows) > n else rows
