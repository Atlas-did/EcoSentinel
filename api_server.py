"""REST API server for the Environmental Monitoring frontend.

Reads from the same log files written by main.py and exposes structured
JSON endpoints consumed by the React dashboard.

Usage:
    python api_server.py              # default: http://0.0.0.0:8080
    python api_server.py --port 8081  # custom port
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Ensure project root is on the Python path
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from energy_system.utils.file_io import read_jsonl
from energy_system.config.config_loader import load_app_config

# ── Config ─────────────────────────────────────────────────────────
cfg, _warnings = load_app_config()

LOG_DIR = _PROJECT_ROOT / "logs"


def _resolve_cors_origins() -> list[str]:
    """Resolve CORS origins from config, with an explicit env override for prod.

    Defaults are local development frontends only. The wildcard ``*`` is never
    emitted with ``allow_credentials=True`` — the config loader already rejects
    that combination.
    """
    env = os.getenv("ECOSENTINEL_CORS_ORIGINS", "").strip()
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    return list(cfg.api.cors_origins)


# ── App ────────────────────────────────────────────────────────────
app = FastAPI(
    title="EcoSentinel API",
    version="2.0.0",
    description="Backend API for EcoSentinel — Smart Environmental Monitoring & AI Energy-Saving System",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_credentials=bool(cfg.api.allow_credentials),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ────────────────────────────────────────────────────────
def _latest_log_path(label: str | None = None) -> Path | None:
    """Find the most recent hardware_<label>.jsonl file."""
    label = label or (cfg.run_label or "saving")
    p = LOG_DIR / f"hardware_{label}.jsonl"
    return p if p.exists() else None


def _read_log_tail(path: Path, n: int = 200) -> list[dict]:
    """Read last N entries from a JSONL log file."""
    rows = read_jsonl(str(path))
    return rows[-n:] if len(rows) > n else rows


def _read_log_last(path: Path) -> dict | None:
    """Read the last entry from a JSONL log file."""
    rows = read_jsonl(str(path), max_lines=1)
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            end = f.tell()
            if end == 0:
                return None
            read_size = min(65536, end)
            f.seek(end - read_size)
            chunk = f.read(read_size)
        text = chunk.decode("utf-8", errors="ignore")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in reversed(lines):
            if ln.startswith("{") and ln.endswith("}"):
                obj = json.loads(ln)
                if isinstance(obj, dict):
                    return obj
    except Exception:
        pass
    return None


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _latest_incidents_path(label: str | None = None) -> Path | None:
    label = label or (cfg.run_label or "saving")
    p = LOG_DIR / f"incidents_{label}.jsonl"
    return p if p.exists() else None


def _daily_summary(label: str | None = None) -> dict | None:
    label = label or (cfg.run_label or "saving")
    d = date.today().isoformat()
    p = LOG_DIR / f"daily_energy_{label}_{d}.json"
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


# ── Endpoints ──────────────────────────────────────────────────────

@app.get("/api/snapshot")
def get_snapshot(label: str | None = None):
    """Return the latest sensor snapshot."""
    path = _latest_log_path(label)
    if not path:
        return {"timestamp": datetime.now().isoformat(), "errors": ["no_log_file"]}
    row = _read_log_last(path)
    if not row:
        return {"timestamp": datetime.now().isoformat(), "errors": ["empty_log"]}
    return {
        "timestamp": row.get("timestamp", datetime.now().isoformat()),
        "temperature": row.get("temperature"),
        "humidity": row.get("humidity"),
        "illuminance": row.get("illuminance"),
        "eco2": row.get("eco2"),
        "bus_v": row.get("bus_v"),
        "current_ma": row.get("current_ma"),
        "power_w": row.get("power_w"),
        "solar_power_w": row.get("solar_power_w"),
        "soc_percent": row.get("soc_percent"),
        "relays": row.get("relays"),
        "curtain_steps": row.get("curtain_steps"),
        "comfort_score": row.get("comfort_score"),
        "safe_mode": row.get("safe_mode"),
        "safe_reason": row.get("safe_reason"),
        "errors": row.get("errors") or [],
    }


@app.get("/api/chart")
def get_chart(
    range: str = Query("1h", alias="range"),
    label: str | None = None,
):
    """Return chart data points from the log."""
    path = _latest_log_path(label)
    if not path:
        return []

    all_rows = _read_log_tail(path, n=200)
    if not all_rows:
        return []

    # Map range to sample count
    count_map = {"5m": 30, "1h": 60, "24h": 200}
    max_count = count_map.get(range, 100)
    rows = all_rows[-max_count:]

    points: list[dict] = []
    for r in rows:
        try:
            ts = r.get("timestamp", "")
        except Exception:
            ts = ""
        points.append({
            "time": ts,
            "temp": r.get("temperature"),
            "humidity": r.get("humidity"),
            "illuminance": r.get("illuminance"),
            "eco2": r.get("eco2"),
            "power_w": r.get("power_w"),
            "solar_power_w": r.get("solar_power_w"),
            "comfort_score": _safe_float(r.get("comfort_score"), 0) * 100
            if r.get("comfort_score") is not None else None,
        })
    return points


@app.get("/api/ai-candidates")
def get_ai_candidates(label: str | None = None):
    """Return AI candidate suggestions from recent log entries."""
    path = _latest_log_path(label)
    if not path:
        return []

    rows = _read_log_tail(path, n=100)
    candidates: list[dict] = []
    seen_ids: set[str] = set()

    for r in reversed(rows):
        cid = r.get("ai_candidate_id")
        source = r.get("ai_source")
        if not cid or cid in seen_ids:
            continue
        seen_ids.add(cid)

        accepted_cmds = r.get("ai_accepted_commands") or []
        rejected_cmds = r.get("ai_rejected_commands") or []

        candidates.append({
            "id": cid,
            "name": r.get("ai_reasoning", f"候选 {cid}")[:40] or f"候选 {cid}",
            "source": source if source in ("cloud", "local_fallback") else "cloud",
            "score": r.get("ai_score"),
            "latency_ms": r.get("ai_latency_ms"),
            "accepted": len(accepted_cmds) > 0,
            "rejected": len(rejected_cmds) > 0,
            "rejectedReason": ", ".join(r.get("ai_reject_reasons") or []) or None,
            "commands": accepted_cmds or r.get("ai_commands") or [],
            "risk": "低",
            "createdAt": r.get("timestamp", datetime.now().isoformat()),
        })

        if len(candidates) >= 10:
            break

    return candidates


@app.get("/api/resilience")
def get_resilience(label: str | None = None):
    """Return self-healing / resilience events."""
    path = _latest_incidents_path(label)
    if not path:
        return []

    rows = _read_log_tail(path, n=50)
    events: list[dict] = []
    for r in rows:
        events.append({
            "incident_id": r.get("incident_id", f"inc-{len(events)}"),
            "state": r.get("resilience_state", "unknown"),
            "action": r.get("action", "unknown"),
            "success": r.get("executed", False),
            "reason": r.get("reason"),
            "timestamp": r.get("ts", datetime.now().isoformat()),
        })
    return events


@app.get("/api/energy-summary")
def get_energy_summary(label: str | None = None):
    """Return baseline vs saving energy comparison."""
    label = label or (cfg.run_label or "saving")

    # Try reading from daily summary files
    today = date.today().isoformat()
    base_path = LOG_DIR / f"daily_energy_baseline_{today}.json"
    save_path = LOG_DIR / f"daily_energy_{label}_{today}.json"

    base_kwh = 0.0
    save_kwh = 0.0

    try:
        if base_path.exists():
            base_kwh = _safe_float(
                json.loads(base_path.read_text(encoding="utf-8")).get("load_energy_wh"), 0
            ) / 1000.0
    except Exception:
        pass

    try:
        daily = _daily_summary(label) or {}
        save_kwh = _safe_float(daily.get("load_energy_wh"), 0) / 1000.0
    except Exception:
        pass

    # Fallback: read from JSONL tails
    if base_kwh == 0.0:
        base_log = LOG_DIR / "hardware_baseline.jsonl"
        if base_log.exists():
            last = _read_log_last(base_log)
            if last:
                base_kwh = _safe_float(last.get("energy_wh"), 0) / 1000.0

    if save_kwh == 0.0:
        save_log = _latest_log_path(label)
        if save_log:
            last = _read_log_last(save_log)
            if last:
                save_kwh = _safe_float(last.get("energy_wh"), 0) / 1000.0

    saving_rate = ((base_kwh - save_kwh) / base_kwh * 100) if base_kwh > 0 else 0.0
    energy_saved = base_kwh - save_kwh
    carbon_factor = 0.5708  # kgCO2/kWh
    electricity_price = 0.80  # CNY/kWh

    return {
        "baseline_kwh": round(base_kwh, 2),
        "saving_kwh": round(save_kwh, 2),
        "saving_rate": round(saving_rate, 1),
        "cost_saved_cny": round(energy_saved * electricity_price, 2),
        "carbon_reduced_kg": round(energy_saved * carbon_factor, 2),
    }


@app.get("/api/health")
def get_health(label: str | None = None):
    """Return system health status inferred from recent log data."""
    path = _latest_log_path(label)
    last = _read_log_last(path) if path else None

    return {
        "serial_connected": bool(last) if last else False,
        "last_heartbeat": (last or {}).get("timestamp", datetime.now().isoformat()),
        "sampling_rate_hz": 1.0,
        "sensors_online": {
            "temperature": last is not None and last.get("temperature") is not None,
            "humidity": last is not None and last.get("humidity") is not None,
            "illuminance": last is not None and last.get("illuminance") is not None,
            "eco2": last is not None and last.get("eco2") is not None,
            "power": last is not None and last.get("power_w") is not None,
            "solar": last is not None and last.get("solar_power_w") is not None,
        },
        "retry_count": 0,
        "self_healing_enabled": cfg.self_healing.enabled,
        "stale_detected": (last or {}).get("safe_mode", False) if last else False,
    }


@app.get("/api/simulation/params")
def get_simulation_params():
    """Return default simulation parameters."""
    return {
        "days": 7,
        "outdoor_temp_base": 28,
        "solar_radiation_max": 1000,
        "building_insulation_r": 3.5,
        "hvac_efficiency": 0.85,
        "occupancy_schedule": "9-18",
        "enable_ai": cfg.ai.enabled,
        "enable_rules": cfg.control.enable_rule_control,
    }


@app.get("/api/ping")
def ping():
    """Health check endpoint."""
    return {"ok": True, "time": datetime.now().isoformat()}


# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="Environmental Monitoring API Server")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind address")
    args = parser.parse_args()

    print(f"Starting API server on http://{args.host}:{args.port}")
    print(f"Log directory: {LOG_DIR}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
