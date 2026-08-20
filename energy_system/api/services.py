"""Business logic for the read-only monitoring API.

Kept separate from HTTP routing so it can be tested without FastAPI/TestClient
and reused by the Streamlit dashboard. All functions read via a
:class:`JsonlTelemetryRepository` and never open log files directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from energy_system.api.schemas import (
    ChartPoint,
    EnergySummary,
    Health,
    SensorHealth,
    SimulationParams,
    Snapshot,
    now_iso,
)
from energy_system.domain.metrics import EnergyAccountingConfig
from energy_system.persistence.jsonl_repository import JsonlTelemetryRepository

# Time-window mapping for the chart endpoint.
RANGE_WINDOW_S = {"5m": 300.0, "1h": 3600.0, "24h": 86400.0}
CHART_MAX_POINTS = 500


def _f(row: dict, *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _parse_ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


class ApiServices:
    def __init__(self, repository: JsonlTelemetryRepository, cfg: Any):
        self.repo = repository
        self.cfg = cfg

    # ── snapshot ──────────────────────────────────────────────────
    def snapshot(self, label: str | None = None) -> Snapshot:
        if not self.repo.has_log(label):
            return Snapshot(timestamp=now_iso(), errors=["no_log_file"])

        row = self.repo.latest(label)
        if not row:
            return Snapshot(timestamp=now_iso(), errors=["empty_log"])

        relays = row.get("relays")
        return Snapshot(
            timestamp=row.get("timestamp") or now_iso(),
            temperature=_f(row, "temperature"),
            humidity=_f(row, "humidity"),
            illuminance=_f(row, "illuminance"),
            eco2=_f(row, "eco2"),
            bus_v=_f(row, "bus_v"),
            current_ma=_f(row, "current_ma"),
            power_w=_f(row, "power_w"),
            solar_power_w=_f(row, "solar_power_w"),
            soc_percent=_f(row, "soc_percent"),
            relays=list(relays) if isinstance(relays, list) else None,
            curtain_steps=_f(row, "curtain_steps"),
            comfort_score=_f(row, "comfort_score"),
            safe_mode=_f(row, "safe_mode"),
            safe_reason=_f(row, "safe_reason"),
            errors=row.get("errors") or [],
        )

    # ── chart ─────────────────────────────────────────────────────
    def chart(self, range_: str = "1h", label: str | None = None) -> list[ChartPoint]:
        window_s = RANGE_WINDOW_S.get(range_)
        if window_s is None:
            result = self.repo.tail(n=100, label=label)
        else:
            result = self.repo.read_since(window_s, label=label)

        rows = result.rows[-CHART_MAX_POINTS:]
        points: list[ChartPoint] = []
        for row in rows:
            comfort = _f(row, "comfort_score")
            points.append(ChartPoint(
                time=row.get("timestamp"),
                temp=_f(row, "temperature"),
                humidity=_f(row, "humidity"),
                illuminance=_f(row, "illuminance"),
                eco2=_f(row, "eco2"),
                power_w=_f(row, "power_w"),
                solar_power_w=_f(row, "solar_power_w"),
                comfort_score=(comfort * 100.0 if comfort is not None else None),
            ))
        return points

    # ── energy summary ────────────────────────────────────────────
    def energy_summary(self, label: str | None = None) -> EnergySummary:
        label = label or self.repo.run_label
        base_kwh = self._kwh_from_daily("baseline") or self._kwh_from_log_tail("baseline")
        save_kwh = self._kwh_from_daily(label) or self._kwh_from_log_tail(label)

        saved = base_kwh - save_kwh
        rate = (saved / base_kwh * 100.0) if base_kwh > 0 else 0.0

        acct = EnergyAccountingConfig.from_settings()

        return EnergySummary(
            baseline_kwh=round(base_kwh, 2),
            saving_kwh=round(save_kwh, 2),
            saving_rate=round(rate, 1),
            energy_saved_kwh=round(saved, 2),
            cost_saved_cny=round(saved * acct.electricity_price_cny_per_kwh, 2),
            carbon_reduced_kg=round(saved * acct.carbon_factor, 2),
            carbon_factor=acct.carbon_factor,
            carbon_factor_source=acct.carbon_factor_source,
            carbon_factor_version=acct.carbon_factor_version,
            electricity_price_cny_per_kwh=acct.electricity_price_cny_per_kwh,
            price_source=acct.price_source,
        )

    def _kwh_from_daily(self, label: str) -> float:
        daily = self.repo.daily_summary(label)
        if not daily:
            return 0.0
        try:
            return float(daily.get("load_energy_wh", 0) or 0) / 1000.0
        except (TypeError, ValueError):
            return 0.0

    def _kwh_from_log_tail(self, label: str) -> float:
        row = self.repo.latest(label)
        if not row:
            return 0.0
        try:
            return float(row.get("energy_wh", 0) or 0) / 1000.0
        except (TypeError, ValueError):
            return 0.0

    # ── health ────────────────────────────────────────────────────
    def health(self, label: str | None = None) -> Health:
        result = self.repo.tail(n=120, label=label)
        last = result.rows[-1] if result.rows else None

        sampling_rate = self._compute_sampling_rate(result.rows)

        return Health(
            serial_connected=bool(last),
            last_heartbeat=(last or {}).get("timestamp"),
            sampling_rate_hz=sampling_rate if sampling_rate is not None else 1.0,
            sensors_online=SensorHealth(
                temperature=last is not None and last.get("temperature") is not None,
                humidity=last is not None and last.get("humidity") is not None,
                illuminance=last is not None and last.get("illuminance") is not None,
                eco2=last is not None and last.get("eco2") is not None,
                power=last is not None and last.get("power_w") is not None,
                solar=last is not None and last.get("solar_power_w") is not None,
            ),
            retry_count=0,
            self_healing_enabled=bool(self.cfg.self_healing.enabled),
            stale_detected=bool((last or {}).get("safe_mode", False)),
            corrupt_records=result.corrupt_records,
        )

    @staticmethod
    def _compute_sampling_rate(rows: list[dict]) -> float | None:
        """Estimate sampling rate (Hz) from timestamps; None when insufficient data."""
        timestamps = [t for t in (_parse_ts(r.get("timestamp")) for r in rows) if t is not None]
        if len(timestamps) < 2:
            return None
        timestamps.sort()
        span_s = (timestamps[-1] - timestamps[0]).total_seconds()
        if span_s <= 0:
            return None
        return (len(timestamps) - 1) / span_s

    # ── simulation params ─────────────────────────────────────────
    def simulation_params(self) -> SimulationParams:
        return SimulationParams(
            enable_ai=bool(self.cfg.ai.enabled),
            enable_rules=bool(self.cfg.control.enable_rule_control),
        )

    # ── ai candidates ─────────────────────────────────────────────
    def ai_candidates(self, label: str | None = None) -> list[dict]:
        result = self.repo.tail(n=100, label=label)
        candidates: list[dict] = []
        seen: set[str] = set()
        for row in reversed(result.rows):
            cid = row.get("ai_candidate_id")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            source = row.get("ai_source")
            accepted = row.get("ai_accepted_commands") or []
            rejected = row.get("ai_rejected_commands") or []
            candidates.append({
                "id": cid,
                "name": (row.get("ai_reasoning") or f"候选 {cid}")[:40] or f"候选 {cid}",
                "source": source if source in ("cloud", "local_fallback") else "cloud",
                "score": row.get("ai_score"),
                "latency_ms": row.get("ai_latency_ms"),
                "accepted": len(accepted) > 0,
                "rejected": len(rejected) > 0,
                "rejectedReason": ", ".join(row.get("ai_reject_reasons") or []) or None,
                "commands": accepted or row.get("ai_commands") or [],
                "risk": "低",
                "createdAt": row.get("timestamp") or now_iso(),
            })
            if len(candidates) >= 10:
                break
        return candidates

    # ── resilience ────────────────────────────────────────────────
    def resilience(self, label: str | None = None) -> list[dict]:
        rows = self.repo.incident_tail(n=50, label=label)
        events: list[dict] = []
        for i, row in enumerate(rows):
            events.append({
                "incident_id": row.get("incident_id", f"inc-{i}"),
                "state": row.get("resilience_state", "unknown"),
                "action": row.get("action", "unknown"),
                "success": row.get("executed", False),
                "reason": row.get("reason"),
                "timestamp": row.get("ts", now_iso()),
            })
        return events
