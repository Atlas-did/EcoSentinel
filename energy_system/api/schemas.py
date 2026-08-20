"""Pydantic response schemas — the single contract between API and frontends.

Field names match the wire format already consumed by the React dashboard so
this refactor is behaviour-preserving. Each model declares types and a
``schema_version``; additive fields (new keys) are safe because the frontend
ignores unknown keys, but renaming a key must update ``types/index.ts`` and the
contract tests in the same change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class ErrorBody(BaseModel):
    """Unified HTTP error envelope."""

    code: str
    message: str
    request_id: str | None = None
    details: Any = None


class Snapshot(BaseModel):
    schema_version: str = SCHEMA_VERSION
    timestamp: str | None = None
    temperature: float | None = None
    humidity: float | None = None
    illuminance: float | None = None
    eco2: float | None = None
    bus_v: float | None = None
    current_ma: float | None = None
    power_w: float | None = None
    solar_power_w: float | None = None
    soc_percent: float | None = None
    relays: list[Any] | None = None
    curtain_steps: int | None = None
    comfort_score: float | None = None
    safe_mode: bool | None = None
    safe_reason: str | None = None
    errors: list[str] = Field(default_factory=list)


class ChartPoint(BaseModel):
    time: str | None = None
    temp: float | None = None
    humidity: float | None = None
    illuminance: float | None = None
    eco2: float | None = None
    power_w: float | None = None
    solar_power_w: float | None = None
    comfort_score: float | None = None  # 0..100 percent


class SensorHealth(BaseModel):
    temperature: bool = False
    humidity: bool = False
    illuminance: bool = False
    eco2: bool = False
    power: bool = False
    solar: bool = False


class Health(BaseModel):
    schema_version: str = SCHEMA_VERSION
    serial_connected: bool = False
    last_heartbeat: str | None = None
    sampling_rate_hz: float | None = None
    sensors_online: SensorHealth = Field(default_factory=SensorHealth)
    retry_count: int = 0
    self_healing_enabled: bool = False
    stale_detected: bool = False
    corrupt_records: int = 0  # additive: number of unreadable JSONL lines


class EnergySummary(BaseModel):
    schema_version: str = SCHEMA_VERSION
    baseline_kwh: float = 0.0
    saving_kwh: float = 0.0
    saving_rate: float = 0.0  # percent, 0..100
    energy_saved_kwh: float = 0.0  # additive
    cost_saved_cny: float = 0.0
    carbon_reduced_kg: float = 0.0
    carbon_factor: float = 0.0  # additive: kgCO2/kWh
    carbon_factor_source: str | None = None  # additive
    electricity_price_cny_per_kwh: float = 0.0  # additive


class Ping(BaseModel):
    ok: bool = True
    time: str


class SimulationParams(BaseModel):
    schema_version: str = SCHEMA_VERSION
    days: int = 7
    outdoor_temp_base: float = 28.0
    solar_radiation_max: float = 1000.0
    building_insulation_r: float = 3.5
    hvac_efficiency: float = 0.85
    occupancy_schedule: str = "9-18"
    enable_ai: bool = False
    enable_rules: bool = True


def now_iso() -> str:
    return datetime.now().isoformat()
