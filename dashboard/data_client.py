"""DashboardDataClient: single read path for the Streamlit dashboard.

Every view reads through this client instead of opening JSONL files directly, so
availability (last-success time + reason) is tracked in one place and a view can
render a clear "data unavailable" state instead of a plausible-looking zero.

The client only reads logs — it never touches the serial port or re-computes
energy/saving metrics (those come from the backend/API summary service).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from dashboard.data_loader import read_daily_summary, read_last_jsonl, read_tail_jsonl
from energy_system.utils.file_io import read_jsonl


@dataclass(frozen=True)
class DataResult:
    """A read result with availability metadata (never silently empty)."""

    data: dict | list | None
    ok: bool
    reason: str | None = None
    last_success_at: float | None = None


class DashboardDataClient:
    """Unified, availability-aware reader for dashboard data sources."""

    def __init__(self, app_root: str | Path, run_label: str = "saving") -> None:
        self.app_root = Path(app_root)
        self.run_label = (run_label or "saving").strip() or "saving"
        self._last_success_at: float | None = None
        self._last_error: str | None = None

    # ── availability state ──────────────────────────────────────────
    @property
    def available(self) -> bool:
        return self._last_success_at is not None

    @property
    def last_success_at(self) -> float | None:
        return self._last_success_at

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _ok(self, data) -> DataResult:
        self._last_success_at = time.time()
        self._last_error = None
        return DataResult(data=data, ok=True, last_success_at=self._last_success_at)

    def _fail(self, reason: str) -> DataResult:
        self._last_error = reason
        return DataResult(data=None, ok=False, reason=reason, last_success_at=self._last_success_at)

    # ── paths ───────────────────────────────────────────────────────
    def _hardware_path(self, label: str | None = None) -> Path:
        return self.app_root / "logs" / f"hardware_{label or self.run_label}.jsonl"

    def _daily_path(self, label: str | None = None) -> Path:
        today = time.strftime("%Y-%m-%d", time.localtime())
        return self.app_root / "logs" / f"daily_energy_{label or self.run_label}_{today}.json"

    # ── reads ───────────────────────────────────────────────────────
    def snapshot(self, label: str | None = None) -> DataResult:
        row = read_last_jsonl(str(self._hardware_path(label)))
        if row is None:
            return self._fail("no_log_data")
        return self._ok(row)

    def tail(self, n: int = 120, label: str | None = None) -> DataResult:
        rows = read_tail_jsonl(str(self._hardware_path(label)), max_rows=n)
        if not rows:
            return self._fail("no_log_data")
        return self._ok(rows)

    def daily_summary(self, label: str | None = None) -> DataResult:
        daily = read_daily_summary(self._daily_path(label))
        if daily is None:
            return self._fail("no_daily_summary")
        return self._ok(daily)

    def baseline_vs_saving(self) -> DataResult:
        base_rows = read_jsonl(str(self._hardware_path("baseline")))
        save_rows = read_jsonl(str(self._hardware_path("saving")))
        if not base_rows or not save_rows:
            return self._fail("missing_baseline_or_saving_log")
        return self._ok({"baseline": base_rows, "saving": save_rows})


__all__ = ["DataResult", "DashboardDataClient"]
