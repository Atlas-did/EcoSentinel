"""Unified metric models for simulation, hardware, and the monitoring API.

``MetricSnapshot`` is the single output structure both the digital-twin simulator
and the live telemetry pipeline use for comfort/energy/battery metrics, so a real
power meter can feed the same data model as the simulator without touching the
controller. ``EnergyAccountingConfig`` is the single source of truth for the
carbon factor and electricity price used in savings summaries, with provenance
(source + version) attached.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from energy_system.config import settings

METRIC_SCHEMA_VERSION = "1.0"

# Canonical units for every MetricSnapshot field. Internal convention: power in
# watts (W), time in seconds (s), energy in watt-hours (Wh) / kilowatt-hours (kWh).
_METRIC_UNITS: dict[str, str] = {
    "comfort_score": "ratio",  # 0..1
    "power_w": "W",
    "energy_wh": "Wh",
    "solar_energy_wh": "Wh",
    "soc_percent": "%",
}


def _opt_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _float(v: Any, default: float = 0.0) -> float:
    f = _opt_float(v)
    return default if f is None else f


@dataclass(frozen=True)
class EnergyAccountingConfig:
    """Carbon factor, electricity price, and metering provenance."""

    carbon_factor: float = 0.5708  # kgCO2/kWh
    carbon_factor_source: str | None = "生态环境部 中国区域电网 2022 平均"
    carbon_factor_version: str | None = "2022"
    electricity_price_cny_per_kwh: float = 0.80  # CNY/kWh
    price_source: str = "demo_default"
    metering_point: str = "lab"
    region: str = "china-south"
    calculation_window: str = "24h"

    @classmethod
    def from_settings(cls) -> "EnergyAccountingConfig":
        """Build from the legacy ``settings`` module (single source of constants)."""
        return cls(
            carbon_factor=float(getattr(settings, "CARBON_FACTOR", 0.5708)),
            carbon_factor_source=getattr(settings, "CARBON_FACTOR_SOURCE", None),
            carbon_factor_version=getattr(settings, "CARBON_FACTOR_VERSION", None),
            electricity_price_cny_per_kwh=float(getattr(settings, "PRICE_CNY_PER_KWH", 0.80)),
            price_source=getattr(settings, "PRICE_SOURCE", "demo_default"),
        )

    def carbon_summary(self) -> dict[str, Any]:
        """Carbon factor with source/version provenance and calculation window."""
        return {
            "value": self.carbon_factor,
            "unit": "kgCO2/kWh",
            "factor_source": self.carbon_factor_source,
            "factor_version": self.carbon_factor_version,
            "calculation_window": self.calculation_window,
        }

    def price_summary(self) -> dict[str, Any]:
        """Electricity price with source provenance and calculation window."""
        return {
            "value": self.electricity_price_cny_per_kwh,
            "unit": "CNY/kWh",
            "factor_source": self.price_source,
            "factor_version": None,
            "calculation_window": self.calculation_window,
        }


@dataclass(frozen=True)
class MetricSnapshot:
    """A single normalized metric summary shared by simulation and telemetry."""

    schema_version: str = METRIC_SCHEMA_VERSION
    comfort_score: float | None = None  # 0..1
    power_w: float | None = None  # W
    energy_wh: float = 0.0  # Wh
    solar_energy_wh: float = 0.0  # Wh
    soc_percent: float | None = None  # %

    UNITS = _METRIC_UNITS

    @classmethod
    def from_sensor(cls, data: dict[str, Any]) -> "MetricSnapshot":
        """Build from a raw/enriched sensor dict (legacy field names)."""
        return cls(
            comfort_score=_opt_float(data.get("comfort_score")),
            power_w=_opt_float(data.get("power_w")),
            energy_wh=_float(data.get("energy_wh")),
            solar_energy_wh=_float(data.get("solar_energy_wh")),
            soc_percent=_opt_float(data.get("soc_percent")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "comfort_score": self.comfort_score,
            "power_w": self.power_w,
            "energy_wh": self.energy_wh,
            "solar_energy_wh": self.solar_energy_wh,
            "soc_percent": self.soc_percent,
        }


def descriptive_stats(
    values: Sequence[float | None],
    *,
    min_samples: int = 30,
) -> dict[str, Any]:
    """Return mean/std/count/95%-CI for a series of metric samples.

    Uses the sample standard deviation (n-1) and a normal-approximation 95%
    confidence interval (z=1.96). When fewer than ``min_samples`` samples are
    present the result is explicitly flagged ``descriptive_only`` so downstream
    consumers do not over-interpret a small-sample mean as a population estimate.
    """
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if n == 0:
        return {"count": 0, "mean": None, "std": None, "ci95": None, "descriptive_only": True}

    mean = sum(vals) / n
    if n < 2:
        return {"count": n, "mean": mean, "std": None, "ci95": None, "descriptive_only": True}

    variance = sum((x - mean) ** 2 for x in vals) / (n - 1)
    std = math.sqrt(variance)
    ci95 = 1.96 * std / math.sqrt(n)
    return {
        "count": n,
        "mean": mean,
        "std": std,
        "ci95": ci95,
        "descriptive_only": n < min_samples,
    }


__all__ = [
    "METRIC_SCHEMA_VERSION",
    "EnergyAccountingConfig",
    "MetricSnapshot",
    "descriptive_stats",
]
