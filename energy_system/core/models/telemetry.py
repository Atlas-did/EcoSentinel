"""Strongly-typed telemetry sample model.

All sensor input — from the serial bridge, the simulator, or tests — is converted
into a :class:`TelemetrySample` before reaching controllers. Missing values are
represented as ``None`` with a quality marker, never silently replaced by defaults
(25°C, 50% humidity, etc.). If a value is estimated, it is flagged via
``field_estimated`` rather than pretending to be a measurement.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any


class SampleQuality(str, Enum):
    OK = "ok"
    MISSING_FIELDS = "missing_fields"
    STALE = "stale"
    INVALID = "invalid"


# Canonical field -> accepted legacy aliases.
_ALIASES: dict[str, tuple[str, ...]] = {
    "temperature_c": ("temperature", "temp", "temperature_c"),
    "humidity_pct": ("humidity", "hum", "humidity_pct"),
    "illuminance_lux": ("illuminance", "lux", "indoor_lux", "illuminance_lux"),
    "eco2_ppm": ("eco2", "eco2_ppm"),
    "tvoc_ppb": ("tvoc", "tvoc_ppb"),
    "power_w": ("power_w",),
    "solar_power_w": ("solar_power_w",),
}


def _as_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


@dataclass(frozen=True)
class TelemetrySample:
    """A single normalized sensor sample."""

    schema_version: str = "1.0"
    timestamp: datetime | None = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    illuminance_lux: float | None = None
    eco2_ppm: float | None = None
    tvoc_ppb: float | None = None
    power_w: float | None = None
    solar_power_w: float | None = None
    relay_states: tuple[int, ...] = ()
    source: str = "unknown"
    quality: SampleQuality = SampleQuality.OK
    field_estimated: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any], source: str = "unknown") -> "TelemetrySample":
        """Build a normalized sample from a raw sensor dict.

        Legacy field names are mapped to canonical names. Missing numeric fields
        stay ``None``; no defaults are fabricated.
        """
        if not isinstance(raw, dict):
            return cls(source=source, quality=SampleQuality.INVALID)

        estimated: list[str] = []
        def _lookup(name: str) -> tuple[bool, Any]:
            aliases = _ALIASES.get(name, (name,))
            for key in aliases:
                if key in raw and raw[key] is not None:
                    return True, raw[key]
            return False, None

        def num(name: str) -> float | None:
            present, v = _lookup(name)
            f = _as_float(v)
            if f is None and present:
                # A field present but non-numeric is an estimate, not a silent drop.
                estimated.append(name)
            return f

        relay_raw = raw.get("relays") or raw.get("relay_states")
        relay_states: tuple[int, ...] = ()
        if isinstance(relay_raw, (list, tuple)):
            relay_states = tuple(1 if r else 0 for r in relay_raw)

        ts = raw.get("timestamp")
        timestamp: datetime | None = None
        if isinstance(ts, datetime):
            timestamp = ts
        elif isinstance(ts, str):
            try:
                timestamp = datetime.fromisoformat(ts)
            except ValueError:
                timestamp = None

        sample = cls(
            timestamp=timestamp,
            temperature_c=num("temperature_c"),
            humidity_pct=num("humidity_pct"),
            illuminance_lux=num("illuminance_lux"),
            eco2_ppm=num("eco2_ppm"),
            tvoc_ppb=num("tvoc_ppb"),
            power_w=num("power_w"),
            solar_power_w=num("solar_power_w"),
            relay_states=relay_states,
            source=source,
            field_estimated=tuple(dict.fromkeys(estimated)),
        )
        return sample.with_quality()

    def with_quality(self) -> "TelemetrySample":
        """Return a copy with a quality flag derived from field presence."""
        critical = (self.temperature_c, self.humidity_pct)
        if any(v is None for v in critical):
            return replace(self, quality=SampleQuality.MISSING_FIELDS)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a canonical JSON-friendly dict."""
        return {
            "schema_version": self.schema_version,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "illuminance_lux": self.illuminance_lux,
            "eco2_ppm": self.eco2_ppm,
            "tvoc_ppb": self.tvoc_ppb,
            "power_w": self.power_w,
            "solar_power_w": self.solar_power_w,
            "relay_states": list(self.relay_states),
            "source": self.source,
            "quality": self.quality.value,
            "field_estimated": list(self.field_estimated),
        }
