"""Log and daily-energy-summary management for EnergySystemApp.

Extracted from main.py to keep the app class focused on orchestration.
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path

from energy_system.utils.file_io import append_jsonl

logger = logging.getLogger("LogManager")


class LogManager:
    """Handles JSONL sampling logs and daily energy summaries."""

    def __init__(self, run_label: str) -> None:
        self.run_label = run_label
        self.log_path = Path("logs") / f"hardware_{run_label}.jsonl"
        self.incidents_path = Path("logs") / f"incidents_{run_label}.jsonl"
        self._ensure_files()

    def _ensure_files(self) -> None:
        """Create log files if they don't exist."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.touch(exist_ok=True)
            self.incidents_path.touch(exist_ok=True)
        except Exception:
            pass

    def log_sample(self, data: dict) -> None:
        """Write a structured sample record to the hardware JSONL log."""
        record = {
            "timestamp": data.get("timestamp"),
            "temperature": data.get("temperature"),
            "humidity": data.get("humidity"),
            "illuminance": data.get("illuminance"),
            "eco2": data.get("eco2"),
            "tvoc": data.get("tvoc"),
            "bus_v": data.get("bus_v"),
            "current_ma": data.get("current_ma"),
            "pwr_mw": data.get("pwr_mw"),
            "power_w": data.get("power_w"),
            "energy_wh": data.get("energy_wh"),
            "solar_bus_v": data.get("solar_bus_v"),
            "solar_current_ma": data.get("solar_current_ma"),
            "solar_pwr_mw": data.get("solar_pwr_mw"),
            "solar_power_w": data.get("solar_power_w"),
            "solar_energy_wh": data.get("solar_energy_wh"),
            "soc_percent": data.get("soc_percent"),
            "comfort_score": data.get("comfort_score"),
            "relays": data.get("relays"),
            "curtain_steps": data.get("curtain_steps"),
            "ai_reasoning": data.get("ai_reasoning"),
            "ai_commands": data.get("ai_commands"),
            "ai_source": data.get("ai_source"),
            "ai_candidate_id": data.get("ai_candidate_id"),
            "ai_latency_ms": data.get("ai_latency_ms"),
            "ai_score": data.get("ai_score"),
            "ai_tuning_event": data.get("ai_tuning_event"),
            "ai_cloud_error": data.get("ai_cloud_error"),
            "ai_accepted_commands": data.get("ai_accepted_commands"),
            "ai_rejected_commands": data.get("ai_rejected_commands"),
            "ai_reject_reasons": data.get("ai_reject_reasons"),
            "safe_mode": data.get("safe_mode"),
            "safe_reason": data.get("safe_reason"),
            "bridge_health": data.get("bridge_health"),
        }
        append_jsonl(str(self.log_path), record)

    def log_incident(self, event: dict) -> None:
        """Write an incident event to the incidents JSONL log."""
        append_jsonl(str(self.incidents_path), event)

    def update_daily_energy(self, data: dict) -> None:
        """Write a daily summary JSON file (no cross-restart accumulation).

        File: logs/daily_energy_<run_label>_YYYY-MM-DD.json
        """
        try:
            d = date.today().isoformat()
            path = Path("logs") / f"daily_energy_{self.run_label}_{d}.json"
            path.parent.mkdir(parents=True, exist_ok=True)

            load_wh = data.get("energy_wh")
            solar_wh = data.get("solar_energy_wh")
            soc = data.get("soc_percent")
            load_wh_f = float(load_wh) if isinstance(load_wh, (int, float)) else 0.0
            solar_wh_f = float(solar_wh) if isinstance(solar_wh, (int, float)) else 0.0
            soc_f = round(float(soc), 2) if isinstance(soc, (int, float)) else None

            obj = {
                "date": d,
                "run_label": self.run_label,
                "updated_at": datetime.now().isoformat(),
                "load_energy_wh": round(load_wh_f, 3),
                "solar_energy_wh": round(solar_wh_f, 3),
                "net_energy_wh": round(load_wh_f - solar_wh_f, 3),
                "soc_percent": soc_f,
                "last_power_w": data.get("power_w"),
                "last_solar_power_w": data.get("solar_power_w"),
            }
            path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            return
